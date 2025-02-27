from pymongo import MongoClient
import os
from pymongo.errors import ConnectionFailure, OperationFailure
from typing import Any, Dict, List, Optional, Callable
from functools import wraps
import json
from bson import json_util



class CRUDDriverMongoDB:
    _instances = {}
    def __init__(self, user: str = None, password: str = None,
                 host: str = 'nv-desktop-services.apporto.com', port: int = 30055,
                 database_name: str = 'AAC', collection_name: str = 'animals') -> None:
        self.user = user if user is not None else os.getenv('MONGO_USER', str(input("Enter MongoDB username: ")))
        self.password = password if password is not None else os.getenv('MONGO_PASS', str(input("Enter MongoDB password: ")))
        self.uri = f'mongodb://{self.user}:{self.password}@{host}:{port}/{database_name}'
        self.database_name = database_name
        self.collection_name = collection_name
        self.client = None
        self.db = None
        self.collection = None
        self.connect()


    def connect(self, database_name: str  = 'AAC', collection_name: str = 'animals') -> None:
        try:
            self.database_name = database_name
            self.collection_name = collection_name
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            self.client.server_info()
            self.db = self.client[self.database_name]
            self.collection = self.db[self.collection_name]
            print(f"Connected to MongoDB: {self.database_name}")
        except ConnectionFailure as e:
            print(f"Connection to MongoDB failed: {e}")
            self.client = None
            self.db = None
            self.collection = None

    @classmethod
    def get_instance(cls, user: str = None, password: str = None,
                     host: str = 'nv-desktop-services.apporto.com', port: int = 30055,
                     database_name: str = 'AAC', collection_name: str = 'animals'):
        key = (user, password, host, port, database_name, collection_name)
        if key not in cls._instances:
            cls._instances[key] = cls(user, password, host, port, database_name, collection_name)
        return cls._instances[key]

    def ensure_instance(func: Callable) -> Callable:
        """
        Decorator to ensure that the MongoDB client and database instances are connected.
        If the client or database is not connected, it attempts to reconnect before
        executing the decorated method.

        Args:
            func (Callable): The function to be decorated.

        Returns:
            Callable: The wrapped function with ensured MongoDB connection.
        """
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if self.client is None or self.db is None:
                self.connect()
            return func(self, *args, **kwargs)
        return wrapper

    def validate_dict_inputs(*dict_args: str):
        """
        Decorator to validate that specified arguments are dictionaries.

        Args:
            *dict_args (str): Names of the arguments to validate.

        Returns:
            Callable: The wrapped function with validated dictionary inputs.
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(self, *args, **kwargs):
                for arg in dict_args:
                    if arg in kwargs and not isinstance(kwargs[arg], dict):
                        print(f"Invalid input: {arg} must be a dictionary.")
                        return False
                return func(self, *args, **kwargs)
            return wrapper
        return decorator

    
    @validate_dict_inputs('document')
    @ensure_instance
    def create(self, collection_name: str, document: Dict[str, Any], database_name: str = None) -> bool:
        if not document:
            print("Invalid data: The document must be a non-empty dictionary.")
            return False
        try:
            collection = self.db[collection_name]
            result = collection.insert_one(document)
            return True if result.inserted_id else False
        except OperationFailure as e:
            print(f"Insert operation failed: {e}")
            return False

    
    @validate_dict_inputs('query')
    @ensure_instance
    def read(self, collection_name: str, query: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        try:
            collection = self.db[collection_name]
            results = list(collection.find(query or {}))
            return [json.loads(json_util.dumps(doc)) for doc in results]  # Best practice
        except OperationFailure as e:
            print(f"Read operation failed: {e}")
            return []


   
    @validate_dict_inputs('query', 'update_values')
    @ensure_instance
    def update(self, collection_name: str, query: Dict[str, Any], update_values: Dict[str, Any]) -> int:
        if not update_values:
            print("Invalid update: 'update_values' must be a non-empty dictionary.")
            return 0
        try:
            collection = self.db[collection_name]
            result = collection.update_many(query, {'$set': update_values})
            return result.modified_count  # Return the number of modified documents
        except OperationFailure as e:
            print(f"Update operation failed: {e}")
            return 0

    @validate_dict_inputs('query')
    @ensure_instance
    def delete(self, collection_name: str, query: Dict[str, Any]) -> int:
        if not query:
            print("Delete operation failed: query cannot be empty.")
            return 0
        try:
            collection = self.db[collection_name]
            result = collection.delete_many(query)
            return result.deleted_count  # Return the number of deleted documents
        except OperationFailure as e:
            print(f"Delete operation failed: {e}")
            return 0

    def __del__(self) -> None:
        if self.client:
            self.client.close()
            print("MongoDB connection closed.")
