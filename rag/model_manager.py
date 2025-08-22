from langchain_community.embeddings import HuggingFaceEmbeddings
from sentence_transformers import CrossEncoder
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)
def load_config():
    config_path = Path(__file__).parent / '../config/config.json'
    with open(config_path, 'r') as f:
        return json.load(f)

config = load_config()
DB_CONFIG = config['database']
MODEL_CONFIG = config['model']
APP_CONFIG = config['app']

class ModelManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_models()
        return cls._instance

    def _init_models(self):
        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name=MODEL_CONFIG['embedding_model'],
                cache_folder=MODEL_CONFIG['cache_path'],
                model_kwargs={"local_files_only": True}
            )
            self.rerank_model = CrossEncoder(
                MODEL_CONFIG['rerank_model'],
                max_length=512,
                cache_folder=MODEL_CONFIG['cache_path'],
                local_files_only=True
            )
            logger.info("Models initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing models: {str(e)}")
            raise


# 单例初始化
model_manager = ModelManager()