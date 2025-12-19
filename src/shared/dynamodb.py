"""DynamoDB utilities and helper functions."""

import os
import boto3
from typing import Any, Dict, List, Optional
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
import logging

from .exceptions import DatabaseError, NotFoundError

logger = logging.getLogger(__name__)


class DynamoDBClient:
    """DynamoDB client wrapper with common operations."""

    def __init__(self, table_name: str):
        """
        Initialize DynamoDB client.

        Args:
            table_name: Name of the DynamoDB table
        """
        self.table_name = table_name

        # Support for LocalStack
        endpoint_url = os.environ.get('LOCALSTACK_ENDPOINT')
        if endpoint_url and os.environ.get('USE_LOCALSTACK', 'false').lower() == 'true':
            self.dynamodb = boto3.resource('dynamodb', endpoint_url=endpoint_url)
        else:
            self.dynamodb = boto3.resource('dynamodb')

        self.table = self.dynamodb.Table(table_name)

    def put_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Put an item in the table.

        Args:
            item: Item to put

        Returns:
            The item that was put

        Raises:
            DatabaseError: If the operation fails
        """
        try:
            # Convert floats to Decimal for DynamoDB
            item = self._python_to_dynamodb(item)
            self.table.put_item(Item=item)
            return item
        except ClientError as e:
            logger.error(f"Error putting item: {e}")
            raise DatabaseError(f"Failed to put item: {str(e)}")

    def get_item(self, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get an item from the table.

        Args:
            key: Primary key of the item

        Returns:
            The item if found, None otherwise

        Raises:
            DatabaseError: If the operation fails
        """
        try:
            response = self.table.get_item(Key=key)
            item = response.get('Item')
            if item:
                return self._dynamodb_to_python(item)
            return None
        except ClientError as e:
            logger.error(f"Error getting item: {e}")
            raise DatabaseError(f"Failed to get item: {str(e)}")

    def update_item(
        self,
        key: Dict[str, Any],
        update_expression: str,
        expression_values: Dict[str, Any],
        expression_names: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Update an item in the table.

        Args:
            key: Primary key of the item
            update_expression: Update expression
            expression_values: Expression attribute values
            expression_names: Optional expression attribute names

        Returns:
            Updated item

        Raises:
            DatabaseError: If the operation fails
        """
        try:
            expression_values = self._python_to_dynamodb(expression_values)

            kwargs = {
                'Key': key,
                'UpdateExpression': update_expression,
                'ExpressionAttributeValues': expression_values,
                'ReturnValues': 'ALL_NEW'
            }

            if expression_names:
                kwargs['ExpressionAttributeNames'] = expression_names

            response = self.table.update_item(**kwargs)
            return self._dynamodb_to_python(response['Attributes'])
        except ClientError as e:
            logger.error(f"Error updating item: {e}")
            raise DatabaseError(f"Failed to update item: {str(e)}")

    def delete_item(self, key: Dict[str, Any]) -> None:
        """
        Delete an item from the table.

        Args:
            key: Primary key of the item

        Raises:
            DatabaseError: If the operation fails
        """
        try:
            self.table.delete_item(Key=key)
        except ClientError as e:
            logger.error(f"Error deleting item: {e}")
            raise DatabaseError(f"Failed to delete item: {str(e)}")

    def query(
        self,
        key_condition_expression: Any,
        filter_expression: Optional[Any] = None,
        index_name: Optional[str] = None,
        limit: Optional[int] = None,
        scan_forward: bool = True,
        exclusive_start_key: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query items from the table.

        Args:
            key_condition_expression: Key condition expression
            filter_expression: Optional filter expression
            index_name: Optional index name
            limit: Optional limit
            scan_forward: Sort order (default: True for ascending)
            exclusive_start_key: Optional pagination key

        Returns:
            Dictionary with items and optional LastEvaluatedKey

        Raises:
            DatabaseError: If the operation fails
        """
        try:
            kwargs = {
                'KeyConditionExpression': key_condition_expression,
                'ScanIndexForward': scan_forward
            }

            if filter_expression:
                kwargs['FilterExpression'] = filter_expression
            if index_name:
                kwargs['IndexName'] = index_name
            if limit:
                kwargs['Limit'] = limit
            if exclusive_start_key:
                kwargs['ExclusiveStartKey'] = exclusive_start_key

            response = self.table.query(**kwargs)

            return {
                'items': [self._dynamodb_to_python(item) for item in response.get('Items', [])],
                'last_evaluated_key': response.get('LastEvaluatedKey')
            }
        except ClientError as e:
            logger.error(f"Error querying items: {e}")
            raise DatabaseError(f"Failed to query items: {str(e)}")

    def scan(
        self,
        filter_expression: Optional[Any] = None,
        limit: Optional[int] = None,
        exclusive_start_key: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Scan items from the table.

        Args:
            filter_expression: Optional filter expression
            limit: Optional limit
            exclusive_start_key: Optional pagination key

        Returns:
            Dictionary with items and optional LastEvaluatedKey

        Raises:
            DatabaseError: If the operation fails
        """
        try:
            kwargs = {}

            if filter_expression:
                kwargs['FilterExpression'] = filter_expression
            if limit:
                kwargs['Limit'] = limit
            if exclusive_start_key:
                kwargs['ExclusiveStartKey'] = exclusive_start_key

            response = self.table.scan(**kwargs)

            return {
                'items': [self._dynamodb_to_python(item) for item in response.get('Items', [])],
                'last_evaluated_key': response.get('LastEvaluatedKey')
            }
        except ClientError as e:
            logger.error(f"Error scanning items: {e}")
            raise DatabaseError(f"Failed to scan items: {str(e)}")

    def batch_write(self, items: List[Dict[str, Any]]) -> None:
        """
        Batch write items to the table.

        Args:
            items: List of items to write

        Raises:
            DatabaseError: If the operation fails
        """
        try:
            with self.table.batch_writer() as batch:
                for item in items:
                    batch.put_item(Item=self._python_to_dynamodb(item))
        except ClientError as e:
            logger.error(f"Error batch writing items: {e}")
            raise DatabaseError(f"Failed to batch write items: {str(e)}")

    @staticmethod
    def _python_to_dynamodb(obj: Any) -> Any:
        """Convert Python objects to DynamoDB compatible format."""
        if isinstance(obj, dict):
            return {k: DynamoDBClient._python_to_dynamodb(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [DynamoDBClient._python_to_dynamodb(item) for item in obj]
        elif isinstance(obj, float):
            return Decimal(str(obj))
        return obj

    @staticmethod
    def _dynamodb_to_python(obj: Any) -> Any:
        """Convert DynamoDB objects to Python format."""
        if isinstance(obj, dict):
            return {k: DynamoDBClient._dynamodb_to_python(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [DynamoDBClient._dynamodb_to_python(item) for item in obj]
        elif isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return obj
