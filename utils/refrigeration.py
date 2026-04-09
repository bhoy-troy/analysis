"""
Zeto API integration module for retrieving premises and cabinet readings.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables from .env file if it exists
load_dotenv()
logger.info("Environment variables loaded")

REFRIGERATION_API_HOST = os.getenv("REFRIGERATION_API_HOST")
REFRIGERATION_READINGS_API_HOST = os.getenv("REFRIGERATION_READINGS_API_HOST")
REFRIGERATION_API_TOKEN = os.getenv("REFRIGERATION_API_TOKEN")

# Log configuration status
if REFRIGERATION_API_HOST:
    logger.info(f"API Host configured: {REFRIGERATION_API_HOST}")
else:
    logger.warning("REFRIGERATION_API_HOST not set")

if REFRIGERATION_READINGS_API_HOST:
    logger.info(f"Readings API Host configured: {REFRIGERATION_READINGS_API_HOST}")
else:
    logger.warning("REFRIGERATION_READINGS_API_HOST not set")

if REFRIGERATION_API_TOKEN:
    logger.info("API Token configured")
else:
    logger.warning("REFRIGERATION_API_TOKEN not set")


class RefrigerationAPIError(Exception):
    """Custom exception for Zeto API errors."""

    pass


def get_api_token() -> str:
    """
    Retrieve the Zeto API token from environment variables.

    Returns:
        str: The API token

    Raises:
        RefrigerationAPIError: If the token is not found in environment variables
    """
    token = os.getenv("REFRIGERATION_API_TOKEN")
    if not token:
        logger.error("API token not found in environment variables")
        raise RefrigerationAPIError("REFRIGERATION_API_TOKEN environment variable not set")
    logger.debug("API token retrieved successfully")
    return token


def _fetch_paginated_results(url: str, headers: Dict[str, str], params: Optional[Dict[str, str]] = None) -> List[Dict]:
    """
    Fetch all results from a paginated API endpoint.

    Args:
        url: Initial API endpoint URL
        headers: Request headers including authorization
        params: Optional query parameters

    Returns:
        List[Dict]: Combined results from all pages

    Raises:
        RefrigerationAPIError: If any API request fails
    """
    all_results = []
    current_url = url
    page_num = 1

    logger.info(f"Starting paginated fetch from: {url}")
    if params:
        logger.debug(f"Request params: {params}")

    try:
        while current_url:
            logger.debug(f"Fetching page {page_num}: {current_url}")

            # Make request to current page
            response = requests.get(
                current_url,
                headers=headers,
                params=params if current_url == url else None,  # Only use params on first request
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()

            # Add results from this page
            results = data.get("results", [])
            all_results.extend(results)
            logger.debug(f"Page {page_num}: Retrieved {len(results)} results")

            # Get next page URL
            current_url = data.get("next")
            page_num += 1

        logger.info(f"Paginated fetch complete: {len(all_results)} total results from {page_num - 1} pages")
        return all_results

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch paginated results: {str(e)}")
        raise RefrigerationAPIError(f"Failed to fetch paginated results: {str(e)}")


def get_premises(company_id=23) -> List[Dict]:
    """
    Pull a list of premises from the Zeto API.
    Automatically handles pagination to retrieve all premises.

    Returns:
        List[Dict]: List of all premises with their details

    Raises:
        RefrigerationAPIError: If the API request fails
    """
    logger.info(f"Fetching premises for company_id: {company_id}")
    token = get_api_token()

    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}

    path = "/api/v4/premises/"
    url = f"{REFRIGERATION_API_HOST}{path}"
    params = {"company": company_id}

    results = _fetch_paginated_results(url, headers, params)
    logger.info(f"Successfully fetched {len(results)} premises")
    return results


def get_units_for_premises(premises_id: Optional[int] = None) -> List[Dict]:
    """
    Pull a list of units from the Zeto API.
    Automatically handles pagination to retrieve all units.

    Args:
        premises_id: Optional premises ID to filter units by specific premises

    Returns:
        List[Dict]: List of all units with their details

    Raises:
        RefrigerationAPIError: If the API request fails
    """
    logger.info(f"Fetching units for premises_id: {premises_id}")
    token = get_api_token()

    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}

    url = f"{REFRIGERATION_API_HOST}/api/v4/unit/"

    params = {}
    if premises_id:
        params["premises_id"] = str(premises_id)

    results = _fetch_paginated_results(url, headers, params)
    logger.info(f"Successfully fetched {len(results)} units for premises {premises_id}")
    return results


def get_cabinet_readings(
    cabinet_id: str, start_date: datetime, end_date: datetime, sensors: Optional[List[int]] = None
) -> List[Dict]:
    """
    Retrieve readings for a specific cabinet within a date range.
    Returns all readings in a single response (not paginated).

    Args:
        cabinet_id: The cabinet identifier
        start_date: Start date for readings (inclusive)
        end_date: End date for readings (inclusive)
        sensors: Optional list of sensor IDs to retrieve (defaults to [0])

    Returns:
        List[Dict]: List of readings for the specified cabinet

    Raises:
        RefrigerationAPIError: If the API request fails
        ValueError: If the date range exceeds 1 month or is invalid
    """
    logger.info(f"Fetching readings for cabinet: {cabinet_id}:sensors from {start_date} to {end_date}")

    # Validate date range
    if end_date < start_date:
        logger.error(f"Invalid date range: end_date ({end_date}) < start_date ({start_date})")
        raise ValueError("End date must be after start date")

    date_diff = end_date - start_date
    if date_diff > timedelta(days=31):
        logger.error(f"Date range too large: {date_diff.days} days (max 31)")
        raise ValueError("Date range cannot exceed 1 month (31 days)")

    logger.debug(f"Date range: {date_diff.days} days")

    token = get_api_token()

    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}

    url = f"{REFRIGERATION_READINGS_API_HOST}/titan/v2/readings/{cabinet_id}/"

    # Convert datetime to Unix timestamp
    from_timestamp = int(start_date.timestamp())
    to_timestamp = int(end_date.timestamp())

    sensor_list = sensors or None
    params = {"from": str(from_timestamp), "to": str(to_timestamp), "langcode": "en-gb", "temperature_uom": "°C"}
    # if sensor_list is not None:
    #     params["sensors"]= ",".join(str(s) for s in sensor_list)

    logger.debug(f"Request URL: {url}")
    logger.debug(f"Request params: {params}")

    try:
        # import pdb
        # pdb.set_trace()
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        # Readings API returns data in "objects" key, not "results"
        readings = data.get("objects", [])
        logger.info(f"Successfully fetched {len(readings)} readings for cabinet {cabinet_id}")
        # yields a list of json objects
        # [{'readings': {'1002': -17.7},
        #   'unit': '0013A2004194B734',
        #   'offset': 0,
        #   'partner-id': 0,
        #   'gateway': 'RMO3218',
        #   'localized_readings': {'1002': '-17.7'},
        #   'ttl': 1933500678,
        #   'id': '0013A2004194B734-1002',
        #   'gain': 1,
        #   'datetime': '2026-04-09 11:28:47',
        #   'timestamp': 1775734127}]

        yield readings

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to retrieve cabinet readings for {cabinet_id}: {str(e)}")
        raise RefrigerationAPIError(f"Failed to retrieve cabinet readings: {str(e)}")


def get_all_cabinet_readings(
    cabinet_ids: List[str], start_date: datetime, end_date: datetime, sensors: Optional[List[int]] = None
) -> Dict[str, List[Dict]]:
    """
    Retrieve readings for multiple cabinets within a date range.
    Automatically handles pagination to retrieve all readings.

    Args:
        cabinet_ids: List of cabinet identifiers
        start_date: Start date for readings (inclusive)
        end_date: End date for readings (inclusive)
        sensors: Optional list of sensor IDs to retrieve (defaults to [0])

    Returns:
        Dict[str, List[Dict]]: Dictionary mapping cabinet IDs to their readings

    Raises:
        RefrigerationAPIError: If any API request fails
        ValueError: If the date range exceeds 1 month or is invalid
    """
    results = {}

    for cabinet_id in cabinet_ids:
        readings = get_cabinet_readings(cabinet_id, start_date, end_date, sensors)
        results[cabinet_id] = readings

    return results
