# app/services/csv_service.py

import pandas as pd
from app.models.convert_job import ConvertJob


class CSVService:
    """
    Serviço responsável por conversões envolvendo CSV.
    """

    # -------------------------
    # CSV → XLSX
    # -------------------------
    @staticmethod
    def convert_csv_to_xlsx(job: ConvertJob, progress=None):

        if progress:
            progress(10, "Lendo arquivo CSV")

        try:
            df = pd.read_csv(job.input_path)

            if progress:
                progress(60, "Gerando planilha XLSX")

            df.to_excel(job.output_path, index=False)

            if progress:
                progress(100, "CSV convertido para XLSX")

        except Exception as e:
            raise RuntimeError(f"Erro ao converter CSV para XLSX: {e}")