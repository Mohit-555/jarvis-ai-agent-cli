import csv
import io

try:
    import pandas as pd
    _HAS_PANDAS = True
except Exception:
    _HAS_PANDAS = False


class CSVParser:
    def parse(self, path):
        with open(path, "r") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def parse_with_pandas(self, path):
        if not _HAS_PANDAS:
            return "pandas not available, use parse() instead"
        df = pd.read_csv(path)
        buf = io.StringIO()
        df.info(buf=buf)
        info = buf.getvalue()
        return f"Shape: {df.shape}\nColumns: {list(df.columns)}\n\n{df.head(10).to_string()}\n\n{info}"
