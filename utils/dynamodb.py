"""
DynamoDB integration module for energy tracking data.
"""

import base64
import json
import logging
import os
import zlib
from collections.abc import Generator
from decimal import Decimal
from typing import Any

import boto3
import boto3.dynamodb.types
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables from .env file if it exists
load_dotenv()
logger.info("Environment variables loaded")

# DynamoDB configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
DYNAMODB_TABLE_ENERGY = os.getenv("DYNAMODB_TABLE_ENERGY", "energy")
DYNAMODB_TABLE_ENERGY_DEV = os.getenv("DYNAMODB_TABLE_ENERGY_DEV", "energy_dev")

# Log configuration status
if AWS_REGION:
    logger.info(f"AWS Region configured: {AWS_REGION}")
if AWS_ACCESS_KEY_ID:
    logger.info("AWS Access Key ID configured")
else:
    logger.warning("AWS_ACCESS_KEY_ID not set")
if AWS_SECRET_ACCESS_KEY:
    logger.info("AWS Secret Access Key configured")
else:
    logger.warning("AWS_SECRET_ACCESS_KEY not set")


class DynamoDBError(Exception):
    """Custom exception for DynamoDB errors."""

    pass


def get_dynamodb_resource():
    """
    Get DynamoDB resource with configured credentials.

    Returns:
        boto3.resource: DynamoDB resource

    Raises:
        DynamoDBError: If credentials are not configured
    """
    try:
        if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
            logger.debug("Creating DynamoDB resource with explicit credentials")
            dynamodb = boto3.resource(
                "dynamodb",
                region_name=AWS_REGION,
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            )
        else:
            logger.debug("Creating DynamoDB resource with default credentials (IAM role/profile)")
            dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)

        logger.info(f"DynamoDB resource created for region: {AWS_REGION}")
        return dynamodb

    except Exception as e:
        logger.error(f"Failed to create DynamoDB resource: {e}")
        raise DynamoDBError(f"Failed to create DynamoDB resource: {e}") from e


def get_table(table_name: str):
    """
    Get a DynamoDB table resource.

    Args:
        table_name: Name of the table

    Returns:
        boto3.resource.Table: DynamoDB table resource

    Raises:
        DynamoDBError: If table cannot be accessed
    """
    try:
        dynamodb = get_dynamodb_resource()
        table = dynamodb.Table(table_name)
        logger.debug(f"Accessed table: {table_name}")
        return table

    except Exception as e:
        logger.error(f"Failed to access table {table_name}: {e}")
        raise DynamoDBError(f"Failed to access table {table_name}: {e}") from e


def python_to_dynamodb(obj: Any) -> Any:
    """
    Convert Python types to DynamoDB compatible types.

    Args:
        obj: Python object to convert

    Returns:
        DynamoDB compatible object
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: python_to_dynamodb(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [python_to_dynamodb(item) for item in obj]
    return obj


def dynamodb_to_python(obj: Any) -> Any:
    """
    Convert DynamoDB types to Python types.

    Args:
        obj: DynamoDB object to convert

    Returns:
        Python object
    """
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: dynamodb_to_python(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [dynamodb_to_python(item) for item in obj]
    return obj


def decompress_blob(blob: dict[str, Any]) -> dict:
    """
    Decompress zlib-compressed binary data from DynamoDB.

    Args:
        blob: Dictionary containing a 'data' field with Binary value

    Returns:
        Decompressed and parsed JSON data

    Raises:
        Exception: If decompression or JSON parsing fails
    """
    raw_bytes = blob["data"].value  # type: ignore[attr-defined]
    decompressed = zlib.decompress(raw_bytes)
    return json.loads(decompressed.decode("utf-8"))  # type: ignore[no-any-return]


def json_serial(obj: Any) -> Any:
    """
    Custom JSON serializer for Decimal and Binary types.

    Args:
        obj: Object to serialize

    Returns:
        JSON-serializable representation

    Raises:
        TypeError: If object type cannot be serialized
    """
    if isinstance(obj, Decimal):
        # Convert Decimal to int if it's an integral value, otherwise float
        if obj == obj.to_integral_value():
            return int(obj)
        return float(obj)

    if isinstance(obj, boto3.dynamodb.types.Binary):
        try:
            # Attempt to decompress and decode as JSON
            decompressed_data = zlib.decompress(obj.value)  # type: ignore[attr-defined]
            return json.loads(decompressed_data.decode("utf-8"))
        except (zlib.error, json.JSONDecodeError, UnicodeDecodeError):
            # If decompression/decoding fails, return base64 encoded string
            return base64.b64encode(obj.value).decode("utf-8")  # type: ignore[attr-defined]

    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def query_by_gateway_and_timestamp(
    table: Any,
    gateway_id: str,
    start_ts: int | float,
    end_ts: int | float,
    index_name: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """
    Query table for items with gateway_id and timestamp range.
    Automatically handles pagination to retrieve all results.

    Args:
        table: boto3 DynamoDB Table resource
        gateway_id: Gateway identifier
        start_ts: Start timestamp (numeric)
        end_ts: End timestamp (numeric)
        index_name: Optional GSI name if gateway_id is a GSI partition key
        limit: Optional maximum items to return (None for unlimited)

    Returns:
        List of decoded Python dict items
    """
    logger.info(f"Querying gateway {gateway_id} from {start_ts} to {end_ts}")

    try:
        start_d = Decimal(str(start_ts))
        end_d = Decimal(str(end_ts))
    except Exception as e:
        logger.error(f"Invalid timestamp bounds: {e}")
        return []

    key_expr = Key("gateway_id").eq(str(gateway_id)) & Key("timestamp").between(start_d, end_d)
    query_kwargs: dict[str, Any] = {"KeyConditionExpression": key_expr}

    if index_name:
        query_kwargs["IndexName"] = index_name
    if limit:
        query_kwargs["Limit"] = int(limit)

    items = []
    try:
        resp = table.query(**query_kwargs)
        raw_items = resp.get("Items", [])
        items.extend(raw_items)

        # Handle pagination
        while resp.get("LastEvaluatedKey"):
            query_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
            resp = table.query(**query_kwargs)
            raw_items = resp.get("Items", [])
            items.extend(raw_items)

        logger.info(f"Retrieved {len(items)} items for gateway {gateway_id}")

    except BotoCoreError as e:
        logger.error(f"DynamoDB query failed: {e}")
        return []

    return items


def get_data_keys(values: list[dict], required_keys: list[str]) -> Generator[dict]:
    """
    Filter values by required keys.

    Args:
        values: List of value dictionaries
        required_keys: List of required key names

    Yields:
        Filtered value dictionaries
    """
    for x in values:
        if x.get("name") in required_keys:
            yield x


def flatten_data(data_blk: dict, required_keys: list[str]) -> list[dict]:
    """
    Flatten nested data structures from DynamoDB items.

    Args:
        data_blk: Data block containing timestamp and values
        required_keys: List of required key names to filter

    Returns:
        List of flattened value dictionaries
    """
    values = data_blk["values"]
    base_values = {"timestamp": data_blk.get("timestamp")}

    new_values = []
    for x in get_data_keys(values, required_keys):
        try:
            new_values.append({**base_values, **x})
        except Exception:
            logger.warning("Failed to flatten value")

    return new_values


def parse_data(item: dict, required_keys: list[str] | None = None) -> list[dict]:
    """
    Parse DynamoDB item with custom JSON serialization.

    Args:
        item: DynamoDB item to parse
        required_keys: Optional list of required keys to filter

    Returns:
        List of parsed and flattened data dictionaries
    """
    keys = required_keys if required_keys is not None else ["Total kW", "Total kVA", "Total kVAr", "Average PF"]

    _data = json.loads(json.dumps(item, default=json_serial))
    return flatten_data(_data, keys)


# ─── Energy Table Operations ──────────────────────────────────────────────


def put_energy_reading(
    gateway_id: str,
    timestamp: int,
    data: dict[str, Any],
    table_name: str = DYNAMODB_TABLE_ENERGY,
) -> dict:
    """
    Store an energy reading in the energy table.

    Args:
        gateway_id: Gateway identifier
        timestamp: Unix timestamp (seconds)
        data: Additional data fields
        table_name: Table name (default: energy)

    Returns:
        dict: Response from DynamoDB

    Raises:
        DynamoDBError: If operation fails
    """
    logger.info(f"Storing energy reading for gateway {gateway_id} at timestamp {timestamp}")

    try:
        table = get_table(table_name)

        item = {
            "gateway_id": gateway_id,
            "timestamp": timestamp,
            **python_to_dynamodb(data),
        }

        response = table.put_item(Item=item)
        logger.debug(f"Successfully stored reading for gateway {gateway_id}")
        return response  # type: ignore[no-any-return]

    except (BotoCoreError, ClientError) as e:
        logger.error(f"Failed to store energy reading: {e}")
        raise DynamoDBError(f"Failed to store energy reading: {e}") from e


def get_energy_reading(
    gateway_id: str,
    timestamp: int,
    table_name: str = DYNAMODB_TABLE_ENERGY,
) -> dict | None:
    """
    Retrieve a specific energy reading.

    Args:
        gateway_id: Gateway identifier
        timestamp: Unix timestamp (seconds)
        table_name: Table name (default: energy)

    Returns:
        dict | None: Reading data or None if not found

    Raises:
        DynamoDBError: If operation fails
    """
    logger.info(f"Retrieving energy reading for gateway {gateway_id} at timestamp {timestamp}")

    try:
        table = get_table(table_name)

        response = table.get_item(Key={"gateway_id": gateway_id, "timestamp": timestamp})

        item = response.get("Item")
        if item:
            logger.debug(f"Found reading for gateway {gateway_id}")
            return dynamodb_to_python(item)  # type: ignore[no-any-return]

        logger.debug(f"No reading found for gateway {gateway_id} at {timestamp}")
        return None

    except (BotoCoreError, ClientError) as e:
        logger.error(f"Failed to retrieve energy reading: {e}")
        raise DynamoDBError(f"Failed to retrieve energy reading: {e}") from e


def query_energy_readings(
    gateway_id: str,
    start_timestamp: int | None = None,
    end_timestamp: int | None = None,
    table_name: str = DYNAMODB_TABLE_ENERGY,
    limit: int | None = None,
) -> list[dict]:
    """
    Query energy readings for a gateway within a time range.

    Args:
        gateway_id: Gateway identifier
        start_timestamp: Start timestamp (inclusive)
        end_timestamp: End timestamp (inclusive)
        table_name: Table name (default: energy)
        limit: Maximum number of items to return

    Returns:
        list[dict]: List of energy readings

    Raises:
        DynamoDBError: If operation fails
    """
    logger.info(f"Querying energy readings for gateway {gateway_id}")
    if start_timestamp and end_timestamp:
        logger.debug(f"Time range: {start_timestamp} to {end_timestamp}")

    try:
        table = get_table(table_name)

        # Build key condition
        if start_timestamp and end_timestamp:
            key_condition = Key("gateway_id").eq(gateway_id) & Key("timestamp").between(start_timestamp, end_timestamp)
        elif start_timestamp:
            key_condition = Key("gateway_id").eq(gateway_id) & Key("timestamp").gte(start_timestamp)
        elif end_timestamp:
            key_condition = Key("gateway_id").eq(gateway_id) & Key("timestamp").lte(end_timestamp)
        else:
            key_condition = Key("gateway_id").eq(gateway_id)  # type: ignore[assignment]

        # Execute query
        query_params: dict[str, Any] = {"KeyConditionExpression": key_condition}
        if limit:
            query_params["Limit"] = limit

        response = table.query(**query_params)
        items = response.get("Items", [])

        logger.info(f"Found {len(items)} readings for gateway {gateway_id}")
        return [dynamodb_to_python(item) for item in items]

    except (BotoCoreError, ClientError) as e:
        logger.error(f"Failed to query energy readings: {e}")
        raise DynamoDBError(f"Failed to query energy readings: {e}") from e


# ─── Energy Dev Table Operations ──────────────────────────────────────────


def put_energy_dev_reading(
    gateway_id: str,
    timestamp: int,
    device_id: int,
    values: str,
    data: dict[str, Any] | None = None,
) -> dict:
    """
    Store an energy reading in the energy_dev table.

    Args:
        gateway_id: Gateway identifier
        timestamp: Unix timestamp (seconds)
        device_id: Device identifier
        values: Values as string
        data: Additional data fields

    Returns:
        dict: Response from DynamoDB

    Raises:
        DynamoDBError: If operation fails
    """
    logger.info(f"Storing dev energy reading for gateway {gateway_id}, device {device_id}")

    try:
        table = get_table(DYNAMODB_TABLE_ENERGY_DEV)

        item = {
            "gateway_id": gateway_id,
            "timestamp": timestamp,
            "device_id": device_id,
            "values": values,
        }

        if data:
            item.update(python_to_dynamodb(data))

        response = table.put_item(Item=item)
        logger.debug(f"Successfully stored dev reading for gateway {gateway_id}")
        return response  # type: ignore[no-any-return]

    except (BotoCoreError, ClientError) as e:
        logger.error(f"Failed to store dev energy reading: {e}")
        raise DynamoDBError(f"Failed to store dev energy reading: {e}") from e


def query_by_device_id(
    device_id: int,
    start_timestamp: int | None = None,
    end_timestamp: int | None = None,
    limit: int | None = None,
) -> list[dict]:
    """
    Query energy readings by device ID using DeviceIdIndex.

    Args:
        device_id: Device identifier
        start_timestamp: Start timestamp (inclusive)
        end_timestamp: End timestamp (inclusive)
        limit: Maximum number of items to return

    Returns:
        list[dict]: List of energy readings

    Raises:
        DynamoDBError: If operation fails
    """
    logger.info(f"Querying energy readings for device {device_id}")

    try:
        table = get_table(DYNAMODB_TABLE_ENERGY_DEV)

        # Build key condition
        if start_timestamp and end_timestamp:
            key_condition = Key("device_id").eq(device_id) & Key("timestamp").between(start_timestamp, end_timestamp)
        elif start_timestamp:
            key_condition = Key("device_id").eq(device_id) & Key("timestamp").gte(start_timestamp)
        elif end_timestamp:
            key_condition = Key("device_id").eq(device_id) & Key("timestamp").lte(end_timestamp)
        else:
            key_condition = Key("device_id").eq(device_id)  # type: ignore[assignment]

        # Execute query on GSI
        query_params: dict[str, Any] = {"IndexName": "DeviceIdIndex", "KeyConditionExpression": key_condition}
        if limit:
            query_params["Limit"] = limit

        response = table.query(**query_params)
        items = response.get("Items", [])

        logger.info(f"Found {len(items)} readings for device {device_id}")
        return [dynamodb_to_python(item) for item in items]

    except (BotoCoreError, ClientError) as e:
        logger.error(f"Failed to query by device ID: {e}")
        raise DynamoDBError(f"Failed to query by device ID: {e}") from e


def query_by_values(
    values: str,
    start_timestamp: int | None = None,
    end_timestamp: int | None = None,
    limit: int | None = None,
) -> list[dict]:
    """
    Query energy readings by values using ValuesIndex.

    Args:
        values: Values string
        start_timestamp: Start timestamp (inclusive)
        end_timestamp: End timestamp (inclusive)
        limit: Maximum number of items to return

    Returns:
        list[dict]: List of energy readings

    Raises:
        DynamoDBError: If operation fails
    """
    logger.info(f"Querying energy readings for values: {values}")

    try:
        table = get_table(DYNAMODB_TABLE_ENERGY_DEV)

        # Build key condition
        if start_timestamp and end_timestamp:
            key_condition = Key("values").eq(values) & Key("timestamp").between(start_timestamp, end_timestamp)
        elif start_timestamp:
            key_condition = Key("values").eq(values) & Key("timestamp").gte(start_timestamp)
        elif end_timestamp:
            key_condition = Key("values").eq(values) & Key("timestamp").lte(end_timestamp)
        else:
            key_condition = Key("values").eq(values)  # type: ignore[assignment]

        # Execute query on GSI
        query_params: dict[str, Any] = {"IndexName": "ValuesIndex", "KeyConditionExpression": key_condition}
        if limit:
            query_params["Limit"] = limit

        response = table.query(**query_params)
        items = response.get("Items", [])

        logger.info(f"Found {len(items)} readings for values: {values}")
        return [dynamodb_to_python(item) for item in items]

    except (BotoCoreError, ClientError) as e:
        logger.error(f"Failed to query by values: {e}")
        raise DynamoDBError(f"Failed to query by values: {e}") from e


# ─── Batch Operations ─────────────────────────────────────────────────────


def batch_put_energy_readings(
    readings: list[dict[str, Any]],
    table_name: str = DYNAMODB_TABLE_ENERGY,
) -> dict:
    """
    Batch write multiple energy readings.

    Args:
        readings: List of readings, each with gateway_id, timestamp, and other fields
        table_name: Table name (default: energy)

    Returns:
        dict: Response with unprocessed items if any

    Raises:
        DynamoDBError: If operation fails
    """
    logger.info(f"Batch storing {len(readings)} energy readings")

    try:
        table = get_table(table_name)

        with table.batch_writer() as batch:
            for reading in readings:
                item = python_to_dynamodb(reading)
                batch.put_item(Item=item)

        logger.info(f"Successfully batch stored {len(readings)} readings")
        return {"UnprocessedItems": []}

    except (BotoCoreError, ClientError) as e:
        logger.error(f"Failed to batch store readings: {e}")
        raise DynamoDBError(f"Failed to batch store readings: {e}") from e


def delete_energy_reading(
    gateway_id: str,
    timestamp: int,
    table_name: str = DYNAMODB_TABLE_ENERGY,
) -> dict:
    """
    Delete a specific energy reading.

    Args:
        gateway_id: Gateway identifier
        timestamp: Unix timestamp (seconds)
        table_name: Table name (default: energy)

    Returns:
        dict: Response from DynamoDB

    Raises:
        DynamoDBError: If operation fails
    """
    logger.info(f"Deleting energy reading for gateway {gateway_id} at timestamp {timestamp}")

    try:
        table = get_table(table_name)

        response = table.delete_item(Key={"gateway_id": gateway_id, "timestamp": timestamp})

        logger.debug(f"Successfully deleted reading for gateway {gateway_id}")
        return response  # type: ignore[no-any-return]

    except (BotoCoreError, ClientError) as e:
        logger.error(f"Failed to delete energy reading: {e}")
        raise DynamoDBError(f"Failed to delete energy reading: {e}") from e
