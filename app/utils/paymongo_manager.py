"""
PayMongo Payment Manager - Handles all PayMongo operations in test mode
Simulates real-world payment processing for capstone project testing
"""

import requests
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from flask import current_app
import base64
import threading
import time

logger = logging.getLogger(__name__)


class PayMongoManager:
    """Manages PayMongo payment operations"""
    
    # Simulated payment states for testing (mimics real PayMongo behavior)
    PAYMENT_STATES = {}  # intent_id -> {'status': str, 'created_at': datetime}
    
    def __init__(self):
        self.api_url = current_app.config.get('PAYMONGO_API_URL', 'https://api.paymongo.com/v1')
        self.secret_key = current_app.config.get('PAYMONGO_SECRET_KEY', '')
        self.public_key = current_app.config.get('PAYMONGO_PUBLIC_KEY', '')
        self.mode = current_app.config.get('PAYMONGO_MODE', 'test')

    def _get_auth_header(self) -> Dict[str, str]:
        """Generate basic auth header for PayMongo API"""
        credentials = base64.b64encode(f"{self.secret_key}:".encode()).decode()
        return {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json"
        }

    def create_payment_intent(
        self,
        amount_cents: int,
        plan: str,
        user_id: int,
        user_email: str,
        description: str = None
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Create a PayMongo payment intent
        
        Args:
            amount_cents: Amount in cents (e.g., 7500 for ₱75)
            plan: Subscription plan (premium/pro)
            user_id: User ID
            user_email: User email
            description: Payment description
            
        Returns:
            Tuple of (success, payment_intent_data, error_message)
        """
        try:
            payload = {
                "data": {
                    "attributes": {
                        "amount": amount_cents,
                        "currency": "PHP",
                        "payment_method_allowed": ["card"],
                        "description": description or f"PetSona {plan.title()} Subscription",
                        "statement_descriptor": f"PETSONA {plan.upper()}",
                        "metadata": {
                            "user_id": str(user_id),
                            "user_email": user_email,
                            "plan": plan,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                }
            }

            logger.info(f"Creating payment intent for user {user_id}, plan {plan}, amount {amount_cents}")
            logger.debug(f"PayMongo API Request: POST {self.api_url}/payment_intents")
            logger.debug(f"Payload: {json.dumps(payload)}")

            response = requests.post(
                f"{self.api_url}/payment_intents",
                headers=self._get_auth_header(),
                json=payload,
                timeout=10
            )

            logger.info(f"PayMongo API Response: Status {response.status_code}")

            if response.status_code in [200, 201]:
                data = response.json()
                intent_id = data.get('data', {}).get('id', '')
                
                # Initialize payment state as 'awaiting_payment_method' (real-world behavior)
                if self.mode == 'test':
                    self.PAYMENT_STATES[intent_id] = {
                        'status': 'awaiting_payment_method',
                        'created_at': datetime.utcnow(),
                        'amount': amount_cents,
                        'plan': plan
                    }
                
                logger.info(f"Payment intent created for user {user_id}: {intent_id}")
                return True, data.get('data'), None
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('errors', [{}])[0].get('detail', response.text)
                except:
                    error_msg = response.text
                logger.error(f"Failed to create payment intent (Status {response.status_code}): {error_msg}")
                logger.error(f"PayMongo API Response Body: {response.text}")
                return False, None, error_msg

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error creating payment intent: {str(e)}")
            return False, None, str(e)
        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            return False, None, str(e)

    def attach_payment_method(
        self,
        payment_intent_id: str,
        payment_method_id: str
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Attach a payment method to a payment intent
        
        Args:
            payment_intent_id: PayMongo payment intent ID
            payment_method_id: PayMongo payment method ID
            
        Returns:
            Tuple of (success, payment_data, error_message)
        """
        try:
            payload = {
                "data": {
                    "attributes": {
                        "payment_method": payment_method_id
                    }
                }
            }

            response = requests.post(
                f"{self.api_url}/payment_intents/{payment_intent_id}/attach",
                headers=self._get_auth_header(),
                json=payload,
                timeout=10
            )

            if response.status_code in [200, 201]:
                data = response.json()
                logger.info(f"Payment method attached to intent {payment_intent_id}")
                return True, data.get('data'), None
            else:
                error_msg = response.text
                logger.error(f"Failed to attach payment method: {error_msg}")
                return False, None, error_msg

        except Exception as e:
            logger.error(f"Error attaching payment method: {str(e)}")
            return False, None, str(e)

    def retrieve_payment_intent(self, payment_intent_id: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Retrieve payment intent details
        
        Args:
            payment_intent_id: PayMongo payment intent ID
            
        Returns:
            Tuple of (success, payment_intent_data, error_message)
        """
        try:
            response = requests.get(
                f"{self.api_url}/payment_intents/{payment_intent_id}",
                headers=self._get_auth_header(),
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return True, data.get('data'), None
            else:
                error_msg = response.text
                logger.error(f"Failed to retrieve payment intent: {error_msg}")
                return False, None, error_msg

        except Exception as e:
            logger.error(f"Error retrieving payment intent: {str(e)}")
            return False, None, str(e)

    def get_payment_status(self, payment_intent_id: str) -> str:
        """
        Get the status of a payment
        
        Args:
            payment_intent_id: PayMongo payment intent ID
            
        Returns:
            Status string (succeeded, failed, processing, awaiting_payment_method)
        """
        success, data, error = self.retrieve_payment_intent(payment_intent_id)
        
        if success and data:
            return data.get('attributes', {}).get('status', 'unknown')
        
        return 'unknown'

    def simulate_successful_payment(self, payment_intent_id: str) -> Dict:
        """
        Simulate a realistic payment transaction (Test Mode Only)
        Returns initial response immediately, updates status via polling
        
        Args:
            payment_intent_id: PayMongo payment intent ID
            
        Returns:
            Initial payment response data (status: processing)
        """
        if self.mode != 'test':
            raise ValueError("Payment simulation only available in test mode")
        
        # Get payment details from state
        payment_info = self.PAYMENT_STATES.get(payment_intent_id, {})
        amount = payment_info.get('amount', 7500)
        plan = payment_info.get('plan', 'premium')
        
        # Update state to 'processing' (real-world behavior)
        self.PAYMENT_STATES[payment_intent_id] = {
            'status': 'processing',
            'created_at': datetime.utcnow(),
            'amount': amount,
            'plan': plan,
            'started_at': datetime.utcnow()
        }
        
        # Start async state transition (2-4 seconds for realistic delay)
        transition_delay = 2.5  # seconds
        self._schedule_payment_completion(payment_intent_id, transition_delay)
        
        # Return immediate response (payment is processing)
        return {
            "id": payment_intent_id,
            "type": "payment_intent",
            "attributes": {
                "amount": amount,
                "currency": "PHP",
                "status": "processing",  # Currently processing
                "description": f"PetSona {plan.title()} Subscription",
                "statement_descriptor": f"PETSONA {plan.upper()}",
                "created_at": int(datetime.utcnow().timestamp()),
                "updated_at": int(datetime.utcnow().timestamp()),
                "payments": []
            }
        }

    def _schedule_payment_completion(self, payment_intent_id: str, delay: float):
        """
        Schedule payment completion after realistic delay
        This mimics real-world payment processing time
        """
        def complete_payment():
            time.sleep(delay)
            payment_info = self.PAYMENT_STATES.get(payment_intent_id, {})
            
            # Update to succeeded state
            self.PAYMENT_STATES[payment_intent_id] = {
                'status': 'succeeded',
                'created_at': payment_info.get('created_at'),
                'amount': payment_info.get('amount', 7500),
                'plan': payment_info.get('plan', 'premium'),
                'started_at': payment_info.get('started_at'),
                'completed_at': datetime.utcnow()
            }
            
            logger.info(f"Simulated payment {payment_intent_id} completed successfully")
        
        # Run in background thread
        thread = threading.Thread(target=complete_payment, daemon=True)
        thread.start()

    def get_simulated_payment_status(self, payment_intent_id: str) -> Dict:
        """
        Get status of a simulated payment (for test mode polling)
        
        Args:
            payment_intent_id: PayMongo payment intent ID
            
        Returns:
            Current payment status information
        """
        payment_info = self.PAYMENT_STATES.get(payment_intent_id, {})
        status = payment_info.get('status', 'unknown')
        amount = payment_info.get('amount', 0)
        plan = payment_info.get('plan', 'premium')
        
        # Build response based on status
        response = {
            "id": payment_intent_id,
            "type": "payment_intent",
            "attributes": {
                "amount": amount,
                "currency": "PHP",
                "status": status,
                "description": f"PetSona {plan.title()} Subscription",
                "created_at": int(datetime.utcnow().timestamp()),
                "updated_at": int(datetime.utcnow().timestamp()),
            }
        }
        
        # Add payment record if completed
        if status == 'succeeded':
            response["attributes"]["payments"] = [
                {
                    "id": f"payment_sim_{payment_intent_id}",
                    "type": "card",
                    "amount": amount,
                    "currency": "PHP",
                    "status": "succeeded",
                    "created_at": int((payment_info.get('completed_at') or datetime.utcnow()).timestamp())
                }
            ]
        else:
            response["attributes"]["payments"] = []
        
        return response

    def create_client_key(self, payment_intent_id: str) -> str:
        """
        Create a client key for PayMongo checkout
        
        Args:
            payment_intent_id: PayMongo payment intent ID
            
        Returns:
            Base64 encoded client key
        """
        try:
            client_key_data = f"{self.public_key}:{payment_intent_id}"
            client_key = base64.b64encode(client_key_data.encode()).decode()
            return client_key
        except Exception as e:
            logger.error(f"Error creating client key: {str(e)}")
            return ""

    def get_test_card_details(self) -> Dict[str, str]:
        """
        Get test card details for PayMongo test mode
        
        Returns:
            Dictionary with test card information
        """
        return {
            "success_card": {
                "number": "4343434343434343",
                "exp_month": "12",
                "exp_year": "25",
                "cvc": "123"
            },
            "fail_card": {
                "number": "4000000000000002",
                "exp_month": "12",
                "exp_year": "25",
                "cvc": "123"
            },
            "3ds_card": {
                "number": "4000002500003155",
                "exp_month": "12",
                "exp_year": "25",
                "cvc": "123"
            }
        }

    def clear_test_state(self):
        """Clear all simulated payment states (useful for testing)"""
        if self.mode == 'test':
            self.PAYMENT_STATES.clear()


def get_paymongo_manager() -> PayMongoManager:
    """Factory function to get PayMongoManager instance"""
    return PayMongoManager()
