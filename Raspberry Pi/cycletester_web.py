import serial
import time
import threading
from flask import Flask, render_template
from flask_socketio import SocketIO
import smtplib
from email.message import EmailMessage

# 1. Setup your credentials and server details
EMAIL_ADDRESS = "guus.van.marle@smarterliving.nl"
EMAIL_PASSWORD = "nrbt nbaw qvrl ehnt"  # Do not use your regular password!

# 2. Create the email container
msg = EmailMessage()
msg['Subject'] = "Cycletester status:"
msg['From'] = EMAIL_ADDRESS
msg['To'] = "engineering@smarterliving.nl"

# --- Configuration ---
PORT_CON = '/dev/ttyACM0'
PORT_NEX = '/dev/ttyAMA5'
BAUD_CON = 115200
BAUD_NEX = 9600

# --- PID Variables ---
kp, ki, kd = 0.1, 0.1, 0.0
setpoint = 150.0
integral = 0
last_error = 0
last_time = time.time()

# --- Stall Configuration ---
STALL_THRESHOLD = 5            # Minimum distance change to consider "moving"
STALL_TIMEOUT = 1.5            # Seconds of no movement before triggering stall

# --- State ---
state = {
    "running": False,
    "counter": 0,
    "dist": 0,
    "last_dist": 0,
    "speed": 0,
    "start_time": 0,
    "door": False,
    "estop": False,
    "L": False,
    "prevL": True,
    "cpm": 0.0,
    "last_cycle_time": 0,
    "stalled": False,
    "last_move_time": 0
}

msg_stalled = """\
<!DOCTYPE html>
<html>
    <body>
        <h1 style="color: Red;">CYCLETESTER STALLED!</h1>
        <h2>Please check machine and restart.</h2>
        <h3>Current cycle count: <b>{count}</b></h3>
        <p>Visit me at <a href>10.181.106.124</a></p>
    </body>
</html>
"""

msg_paused = """\
<!DOCTYPE html>
<html>
    <body>
        <h1 style="color: Orange;">CYCLETESTER PAUSED!</h1>
        <h2>Please replace pins and continue test.</h2>
        <h3>Current cycle count: <b>{count}</b></h3>
        <p>Visit me at <a href>10.181.106.124</a></p>
    </body>
</html>
"""
msg_finished = """\
<!DOCTYPE html>
<html>
    <body>
        <h1 style="color: Limegreen;">CYCLETESTER FINISHED!</h1>
        <h2>Test completed.</h2>
        <h3>Current cycle count: <b>{count}</b></h3>
        <p>Visit me at <a href>10.181.106.124</a></p>
    </body>
</html>
"""

messages = [msg_stalled, msg_paused, msg_finished]

# --- Web Setup ---
app = Flask(__name__)
# threading mode is more stable for standard Python installs
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# --- Serial Setup ---
try:
    ser_con = serial.Serial(PORT_CON, BAUD_CON, timeout=0.01)
    ser_nex = serial.Serial(PORT_NEX, BAUD_NEX, timeout=0.01)
    print(f"✅ Hardware Serial Connected")
except Exception as e:
    print(f"❌ Serial Error: {e}")
    ser_con = None
    ser_nex = None

def send_status_email(template_index):
    """Sends a formatted email based on the current state counter."""
    try:
        msg = EmailMessage()
        
        msg.set_content(messages[template_index].format(count=state['counter']), subtype='html')

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        print(f"📧 Email Notification Sent (Type {template_index})")
    except Exception as e:
        print(f"❌ Email Failed: {e}")

def send_con(cmd, val):
    if ser_con:
        ser_con.write(f"{cmd}{val}\n".encode())
        
def send_nex(cmd):
    """Sends command to Nextion with required 3-byte termination"""
    # Create the termination sequence as a bytes object
    eof = b'\xff\xff\xff'
    # Encode the command string and add the bytes
    full_cmd = cmd.encode('ascii') + eof
    ser_nex.write(full_cmd)
        
def process_controllino_line(line):
    """Parses: DATA:L:0,M:0,R:0,D:450,E:1"""
    if line.startswith("DATA:"):
        try:
            # Strip the prefix and split
            clean_line = line.replace("DATA:", "")
            parts = dict(x.split(':') for x in clean_line.split(','))
            
            # Update state
            state['dist'] = int(parts.get('D', 0))
            state['estop'] = parts.get('E') == '0' # Assuming 0 is E-STOP active
            state['L'] = parts.get('L') == '1'
            state['door'] = int(parts.get('S',0)) < 500
            if state['L'] and not state['prevL']: # Cycle sensor
                state['counter'] += 1
                send_nex(f"n0.val={state['counter']}")
                
                # Check for specific milestones: 100 or 2500
                if state['counter'] in [100, 2500]:
                    print(f"⏸️ Milestone {state['counter']} reached. Triggering Pause.")
                    state['running'] = False
                    send_con('S', 0)
                    send_con('M', 0)
                    send_nex("t0.txt=\"PAUSED: PIN REPLACE\"")
                    send_status_email(1) # Send msg_paused
            state['prevL'] = state['L']
        except Exception as e:
            print(f"Parsing Error: {e} | Line: {line}")

def process_nextion_input(raw):
    """Handles incoming Nextion touch events"""
    # (Trigger 0) STOP
    if b'\x00' in raw:
        state['running'] = False
        state['stalled'] = False
        send_con('S', 0)
        send_con('M', 0) # Magnet OFF
        print("⏹️ Machine Stopped")
    # (Trigger 1) START
    if b'\x01' in raw and not state['door']:
        state['running'] = True
        state['stalled'] = False
        state['start_time'] = time.time()
        send_con('M', 1) # Magnet ON
        print("▶️ Machine Started")
        
def calculate_pid(current_speed):
    global integral, last_error, last_time
    now = time.time()
    dt = now - last_time
    if dt <= 0: return 70
    
    error = setpoint - current_speed
    integral += error * dt
    integral = max(min(integral, 100), -100) # Windup protection
    
    derivative = (error - last_error) / dt
    output = (kp * error) + (ki * integral) + (kd * derivative)
    
    last_error = error
    last_time = now
    return int(max(min(output, 200), 70))
    
def reset_machine():
    """Clears error states and resets timers for a fresh start"""
    state['stalled'] = False
    state['running'] = False
    state['last_move_time'] = time.time()
    state['counter'] = 0
    # Clear the error message on Nextion (assuming t0 is your status label)
    send_nex("t0.txt=\"Ready\"")
    print("🔄 Machine State Reset")
    
def check_stall():
    """Checks if the machine is powered but not physically moving"""
    now = time.time()
    
    # Only check for stalls if we've been running for at least 1 second 
    # (to allow for initial inertia/soft start)
    if state['running'] and (now - state['start_time'] > 1.0):
        dist_change = abs(state['dist'] - state['last_dist'])
        
        if dist_change > STALL_THRESHOLD:
            state['last_move_time'] = now
            state['stalled'] = False
        else:
            # If the time since the last real movement exceeds our timeout
            if now - state['last_move_time'] > STALL_TIMEOUT:
                return True
    else:
        # If not running, reset the move timer to current time
        state['last_move_time'] = now
        
    return False

def background_loop():
    """Main machine logic + throttled web updates"""
    print("🚀 Background thread started...")
    last_web_update = 0
    
    while True:
        # 1. Handle Serial Input (High Speed)
        if ser_con and ser_con.in_waiting:
            # Prevent lag: if buffer is huge, skip to the latest data
            if ser_con.in_waiting > 1000:
                ser_con.reset_input_buffer()

            line = ser_con.readline().decode('utf-8', errors='ignore').strip()
            #print(f"DEBUG CON: {line}") # Uncomment to see raw sensor stream
            process_controllino_line(line)
            
        # 2. Read from Nextion
        if ser_nex.in_waiting:
            raw_nex = ser_nex.read(ser_nex.in_waiting)
            process_nextion_input(raw_nex)

        # 3. Control Logic
        if state['running'] and not state['estop'] and not state['door']:
            # --- STALL DETECTION LOGIC ---
            if check_stall():
                print("⚠️ STALL DETECTED! Shutting down motor.")
                state['running'] = False
                state['stalled'] = True
                send_con('S', 0)      # Stop Motor
                send_con('M', 0)      # Magnet OFF (Safety)
                send_nex("t0.txt=\"STALL ERROR\"") # Assuming t0 is a status text on Nextion
                send_status_email(0)
                continue # Skip the rest of the movement logic
            # -----------------------------
            
            
            
            now = time.time()
            # Calculate Speed (Delta Dist / 50ms)
            dist_diff = abs(state['dist'] - state['last_dist'])
            state['speed'] = dist_diff / 0.05 
            state['last_dist'] = state['dist']

            # Soft Start Ramp (first 2 seconds)
            elapsed = now - state['start_time']
            if elapsed < 2.0:
                pwm_out = int(70 + (elapsed / 2.0) * 50) # Ramp from 70 to 120
            else:
                pwm_out = calculate_pid(state['speed'])
            
            # Travel end boost
            if state['dist'] > 250 or state['dist'] < 130:
                pwm_out = int(pwm_out * 1.2)

            send_con('W', 100)
        else:
            send_con('S', 0)
            if state['estop'] or state['door']:
                state['running'] = False

        # 4. Throttled Web Updates (5Hz)
        # This fixes the 'laggy' refresh by not flooding the browser
        now = time.time()
        if now - last_web_update > 0.2: 
            socketio.emit('update', state)
            last_web_update = now

        # Tiny sleep to let the CPU breathe
        time.sleep(0.01)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('web_cmd')
def handle_web_cmd(cmd):
    print(f"🌐 Web Command Received: {cmd}")
    if cmd == 'start':
        if not state['door']:
            state['running'] = True
            state['stalled'] = False
            state['start_time'] = time.time()
            print("Machine Starting...")
        else:
            print("Cannot start: Door is open")
    elif cmd == 'stop':
        state['running'] = False
        state['stalled'] = False
        send_con('S', 0)
        print("Machine Stopped")
    elif cmd == 'reset':
        reset_machine()

if __name__ == '__main__':
    # Use daemon=True so the thread dies when you stop the script
    t = threading.Thread(target=background_loop, daemon=True)
    t.start()
    
    print("--- Starting Server on http://0.0.0.0:5000 ---")
    # debug=False is important when using threading to avoid double-starting
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
