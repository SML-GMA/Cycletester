from codaio import Coda, Document

# Initialize by providing a coda object directly
coda = Coda('YOUR_API_KEY')

doc = Document('YOUR_DOC_ID', coda=coda)

# Or initialiaze from environment by storing your API key in environment variable `CODA_API_KEY`
doc = Document.from_environment('YOUR_DOC_ID')

doc.list_tables()

table = doc.get_table('TABLE_ID')