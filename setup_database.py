import pymongo
from pymongo.errors import ConnectionFailure

def setup_db():
    """
    Connects to MongoDB and ensures the database and collections exist.
    """
    try:
        # --- 1. Connect to the local MongoDB server ---
        # Replace the local connection with your Atlas SRV string
        client = pymongo.MongoClient("mongodb+srv://dairy_system:Rajat2001@cluster0.gplhuqg.mongodb.net/?appName=Cluster0")
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