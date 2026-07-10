# app/services/xlsx_service.py

import pandas as pd
from app.models.convert_job import ConvertJob


class XLSXService:
    """
    Serviço responsável por conversões envolvendo XLSX.
    """

    # -------------------------
    # XLSX → CSV
    # -------------------------
    @staticmethod
    def convert_xlsx_to_csv(job: ConvertJob, progress=None):

        if progress:
            progress(10, "Abrindo planilha XLSX")

        try:
            df = pd.read_excel(job.input_path)

            if progress:
                progress(60, "Convertendo para CSV")

            df.to_csv(job.output_path, index=False)

            if progress:
                progress(100, "XLSX convertido para CSV")

        except Exception as e:
            raise RuntimeError(f"Erro ao converter XLSX para CSV: {e}")