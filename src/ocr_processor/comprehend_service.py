"""AWS Comprehend service for expense categorization."""

import os
import boto3
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

# Category mapping based on keywords
CATEGORY_KEYWORDS = {
    "Food & Dining": [
        'restaurant', 'cafe', 'coffee', 'food', 'dining', 'pizza', 'burger',
        'sushi', 'bar', 'pub', 'diner', 'grill', 'kitchen', 'bistro', 'eatery',
        'mcdonald', 'starbucks', 'subway', 'chipotle', 'taco', 'bakery'
    ],
    "Groceries": [
        'grocery', 'supermarket', 'market', 'walmart', 'target', 'costco',
        'whole foods', 'trader joe', 'kroger', 'safeway', 'albertsons',
        'fresh', 'organic', 'produce'
    ],
    "Transportation": [
        'uber', 'lyft', 'taxi', 'gas', 'fuel', 'parking', 'transit', 'metro',
        'bus', 'train', 'airline', 'flight', 'car rental', 'toll', 'auto',
        'shell', 'chevron', 'exxon', 'bp', 'mobil'
    ],
    "Shopping": [
        'amazon', 'ebay', 'mall', 'store', 'shop', 'retail', 'clothing',
        'fashion', 'apparel', 'shoes', 'electronics', 'best buy', 'apple store',
        'nike', 'adidas', 'zara', 'h&m', 'department'
    ],
    "Entertainment": [
        'movie', 'theater', 'cinema', 'netflix', 'spotify', 'game', 'concert',
        'ticket', 'show', 'museum', 'park', 'amusement', 'entertainment',
        'streaming', 'subscription', 'hulu', 'disney'
    ],
    "Utilities": [
        'electric', 'water', 'gas', 'utility', 'power', 'internet', 'cable',
        'phone', 'mobile', 'telecom', 'att', 'verizon', 't-mobile', 'comcast',
        'spectrum'
    ],
    "Healthcare": [
        'hospital', 'clinic', 'doctor', 'medical', 'pharmacy', 'cvs', 'walgreens',
        'health', 'dental', 'vision', 'medicine', 'prescription', 'insurance',
        'lab', 'urgent care'
    ],
    "Travel": [
        'hotel', 'motel', 'airbnb', 'resort', 'booking', 'expedia', 'travel',
        'vacation', 'trip', 'marriott', 'hilton', 'hyatt', 'rental car',
        'cruise', 'tour'
    ],
    "Education": [
        'school', 'university', 'college', 'tuition', 'education', 'books',
        'textbook', 'course', 'training', 'learning', 'udemy', 'coursera',
        'class', 'seminar', 'workshop'
    ]
}


class ComprehendService:
    """AWS Comprehend client wrapper for expense categorization."""

    def __init__(self):
        """Initialize Comprehend client."""
        # Support for LocalStack
        endpoint_url = os.environ.get('LOCALSTACK_ENDPOINT')
        if endpoint_url and os.environ.get('USE_LOCALSTACK', 'false').lower() == 'true':
            self.client = boto3.client('comprehend', endpoint_url=endpoint_url)
        else:
            self.client = boto3.client('comprehend')

        self.confidence_threshold = float(
            os.environ.get('COMPREHEND_CONFIDENCE_THRESHOLD', '70')
        )

    def categorize_expense(
        self,
        merchant: Optional[str],
        items: list,
        raw_text: str
    ) -> Dict[str, Any]:
        """
        Categorize expense using merchant name, items, and text.

        Args:
            merchant: Merchant name
            items: List of line items
            raw_text: Raw OCR text

        Returns:
            Category and confidence score
        """
        # First, try keyword-based categorization (faster and more reliable)
        keyword_result = self._categorize_by_keywords(merchant, items, raw_text)

        if keyword_result['confidence'] >= 80:
            logger.info(f"Categorized by keywords: {keyword_result['category']}")
            return keyword_result

        # Fallback to Comprehend entity detection
        try:
            comprehend_result = self._categorize_by_comprehend(merchant, raw_text)

            # Use the result with higher confidence
            if comprehend_result['confidence'] > keyword_result['confidence']:
                logger.info(f"Categorized by Comprehend: {comprehend_result['category']}")
                return comprehend_result
            else:
                logger.info(f"Using keyword categorization: {keyword_result['category']}")
                return keyword_result

        except Exception as e:
            logger.warning(f"Comprehend categorization failed: {str(e)}")
            # Fall back to keyword result
            return keyword_result

    def _categorize_by_keywords(
        self,
        merchant: Optional[str],
        items: list,
        raw_text: str
    ) -> Dict[str, Any]:
        """
        Categorize based on keyword matching.

        Args:
            merchant: Merchant name
            items: List of line items
            raw_text: Raw OCR text

        Returns:
            Category and confidence score
        """
        # Combine all text
        text_to_analyze = ' '.join(filter(None, [
            merchant or '',
            raw_text,
            ' '.join(item.get('description', '') for item in items if item)
        ])).lower()

        # Score each category
        category_scores = {}

        for category, keywords in CATEGORY_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                if keyword in text_to_analyze:
                    # Weight merchant name matches higher
                    if merchant and keyword in merchant.lower():
                        score += 3
                    else:
                        score += 1

            if score > 0:
                category_scores[category] = score

        # Find category with highest score
        if category_scores:
            best_category = max(category_scores.items(), key=lambda x: x[1])
            category_name = best_category[0]
            score = best_category[1]

            # Calculate confidence (cap at 95%)
            confidence = min(score * 15, 95)

            return {
                'category': category_name,
                'confidence': confidence,
                'method': 'keywords'
            }

        # Default category
        return {
            'category': 'Other',
            'confidence': 50,
            'method': 'default'
        }

    def _categorize_by_comprehend(
        self,
        merchant: Optional[str],
        raw_text: str
    ) -> Dict[str, Any]:
        """
        Categorize using AWS Comprehend entity detection.

        Args:
            merchant: Merchant name
            raw_text: Raw OCR text

        Returns:
            Category and confidence score
        """
        try:
            # Prepare text for analysis
            text_to_analyze = merchant or raw_text or "Unknown"

            # Truncate if too long (Comprehend has a 5000 byte limit)
            if len(text_to_analyze) > 5000:
                text_to_analyze = text_to_analyze[:5000]

            # Detect entities
            response = self.client.detect_entities(
                Text=text_to_analyze,
                LanguageCode='en'
            )

            entities = response.get('Entities', [])

            # Look for organization entities (merchants)
            organizations = [
                e for e in entities
                if e['Type'] == 'ORGANIZATION' and e['Score'] >= self.confidence_threshold / 100
            ]

            if organizations:
                # Use the entity with highest score
                best_entity = max(organizations, key=lambda x: x['Score'])
                entity_text = best_entity['Text'].lower()

                # Match entity to category
                for category, keywords in CATEGORY_KEYWORDS.items():
                    for keyword in keywords:
                        if keyword in entity_text:
                            return {
                                'category': category,
                                'confidence': best_entity['Score'] * 100,
                                'method': 'comprehend'
                            }

            # If no good match, return default
            return {
                'category': 'Other',
                'confidence': 60,
                'method': 'comprehend_default'
            }

        except ClientError as e:
            logger.error(f"Comprehend API error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Comprehend categorization: {str(e)}")
            raise

    def detect_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Detect sentiment of text (for future use).

        Args:
            text: Text to analyze

        Returns:
            Sentiment analysis result
        """
        try:
            # Truncate if too long
            if len(text) > 5000:
                text = text[:5000]

            response = self.client.detect_sentiment(
                Text=text,
                LanguageCode='en'
            )

            return {
                'sentiment': response['Sentiment'],
                'scores': response['SentimentScore']
            }

        except ClientError as e:
            logger.error(f"Sentiment detection error: {str(e)}")
            raise
