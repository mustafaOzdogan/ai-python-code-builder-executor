import os

from dotenv import load_dotenv


load_dotenv()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4o-mini",
)

CODE_WORK_DIR = os.getenv(
    "CODE_WORK_DIR",
    "working",
)

CODE_PREVIEW_MAX_LINES = int(
    os.getenv("CODE_PREVIEW_MAX_LINES", "50"),
)

CODE_PREVIEW_HEAD_LINES = int(
    os.getenv("CODE_PREVIEW_HEAD_LINES", "25"),
)

CODE_PREVIEW_TAIL_LINES = int(
    os.getenv("CODE_PREVIEW_TAIL_LINES", "25"),
)

MAX_FAILED_EXECUTIONS = int(
    os.getenv("MAX_FAILED_EXECUTIONS", "3"),
)

MAX_TURNS = int(
    os.getenv("MAX_TURNS", "12"),
)
