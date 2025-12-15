from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError


def _build_client(uri, username, password):
    connection_string = f"mongodb+srv://{username}:{password}@{uri}"
    return MongoClient(connection_string, serverSelectionTimeoutMS=5000)


def test_mongodb_connection(uri, username, password):
    """Lightweight connectivity probe."""
    client = None
    try:
        client = _build_client(uri, username, password)
        client.admin.command("ping")
        print("✓ Successfully connected to MongoDB")
        databases = client.list_database_names()
        print(f"✓ Available databases: {databases}")
        return True
    except ConnectionFailure as e:
        print(f"✗ Connection failed: {e}")
        return False
    except ServerSelectionTimeoutError as e:
        print(f"✗ Server selection timeout: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        if client:
            client.close()


def fetch_portfolio_intelligence(uri, username, password, limit=5):
    """Read sample documents from Project3.PortfolioIntelligence without embeddings."""
    client = None
    try:
        client = _build_client(uri, username, password)
        client.admin.command("ping")
        collection = client["Project3"]["PortfolioIntelligence"]
        count = collection.estimated_document_count()
        print(f"✓ PortfolioIntelligence estimated count: {count}")
        projection = {"_id": 0, "embeddings": 0, "production_embedding": 0}
        docs = list(collection.find({}, projection).limit(limit))
        if not docs:
            print("No documents returned.")
        else:
            for idx, doc in enumerate(docs, start=1):
                print(f"--- Document {idx} ---")
                print(doc)
        return docs
    except Exception as e:
        print(f"✗ Error reading collection: {e}")
        return []
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    URI = "biaproject2.zxuzaya.mongodb.net/"
    USERNAME = "profLow"
    PASSWORD = "didWeCook"

    if test_mongodb_connection(URI, USERNAME, PASSWORD):
        fetch_portfolio_intelligence(URI, USERNAME, PASSWORD, limit=5)