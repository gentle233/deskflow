"""文件操作封装 - 读取各种格式文件"""
import os

class FileOps:
    """统一文件读取接口，支持多种格式"""

    @staticmethod
    def read(path: str) -> str:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".txt":
            return FileOps._read_txt(path)
        elif ext == ".md":
            return FileOps._read_txt(path)
        elif ext == ".pdf":
            return FileOps._read_pdf(path)
        elif ext == ".docx":
            return FileOps._read_docx(path)
        elif ext in (".xlsx", ".xls", ".csv"):
            return FileOps._read_excel(path)
        else:
            return FileOps._read_txt(path)

    @staticmethod
    def _read_txt(path: str) -> str:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    @staticmethod
    def _read_pdf(path: str) -> str:
        from pypdf import PdfReader
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    @staticmethod
    def _read_docx(path: str) -> str:
        from docx import Document
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)

    @staticmethod
    def _read_excel(path: str) -> str:
        import pandas as pd
        if path.endswith(".csv"):
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path, sheet_name=None)
            if isinstance(df, dict):
                result = []
                for name, sheet in df.items():
                    result.append(f"=== Sheet: {name} ===")
                    result.append(sheet.to_csv(index=False))
                return "\n".join(result)
            return df.to_csv(index=False)
        return df.to_csv(index=False)

    @staticmethod
    def write(path: str, content: str):
        """写文件（支持 txt/md）"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
