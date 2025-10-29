import pymongo
from pymongo.errors import ConnectionFailure
import os
from dotenv import load_dotenv

def setup_db():
    """
    Connects to MongoDB and ensures the database and collections exist.
    """
    try:
        # --- 1. Connect to the local MongoDB server ---
        # Replace the local connection with your Atlas SRV string
  
 
load_dotenv()
        MONGO_URI = os.getenv("MONGO_URI")
        client: MongoClient = MongoClient(MONGO_URI)
        
        # The ismaster command is cheap and does not require auth.
        client.admin.command('ismaster')
        print("--- Successfully connected to MongoDB! ---")

    except ConnectionFailure as e:
        print(f"Error: Could not connect to MongoDB. {e}")
        return

    # --- 2. Define names and get a handle for the database ---
    DB_NAME = "dairy_project"
    db = client[DB_NAME]

    CUSTOMERS_COLLECTION = "customers"
    VARIATIONS_COLLECTION = "daily_variations"

    # --- 4. Verify and print the final state ---
    print(f"\nFinal collections in '{DB_NAME}': {db.list_collection_names()}")
    print("\n--- Database setup is complete! ---")

    # Close the connection
    client.close()


if __name__ == "__main__":

    setup_db()
