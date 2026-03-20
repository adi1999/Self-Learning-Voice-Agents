"""MongoDB connection and collection references."""

from pymongo import MongoClient

from config.settings import MONGO_DB_NAME, MONGO_URI

client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]

agent_versions_collection = db["agent_versions"]
conversations_collection = db["conversations"]
evolution_runs_collection = db["evolution_runs"]
strategy_tactics_collection = db["strategy_tactics"]
failed_approaches_collection = db["failed_approaches"]
