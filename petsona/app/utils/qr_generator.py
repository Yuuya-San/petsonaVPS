"""
QR Code Generator with Logo
Generates QR codes with embedded logos for booking receipts
"""

import os
import qrcode
from PIL import Image # pyright: ignore[reportMissingImports]
import json
from typing import Dict, Optional


class QRCodeGenerator:
    """Generate QR codes with logos for booking receipts"""
    
    def __init__(self, app=None):
        self.app = app
        self.logo_path = None
        self.upload_dir = None
        
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
        self.logo_path = os.path.join(
            app.static_folder, 
            'images', 
            'logo', 
            'petsona-logo.png'
        )
        self.upload_dir = os.path.join(
            app.static_folder,
            'uploads',
            'qr_codes'
        )
        # Create directory if it doesn't exist
        os.makedirs(self.upload_dir, exist_ok=True)
    
    def generate_booking_qr(self, booking_id: int, booking_number: str, booking_status: str,
                           confirmation_code: str, merchant_name: str,
                           appointment_date: str, appointment_time: str) -> Optional[str]:
        """
        Generate QR code for booking receipt
        
        Args:
            booking_id: Booking database ID
            booking_number: Booking reference number
            booking_status: Status of the booking
            confirmation_code: Confirmation code
            merchant_name: Merchant business name
            appointment_date: Appointment date
            appointment_time: Appointment time
            
        Returns:
            URL path to generated QR code image or None if failed
        """
        try:
            # Prepare QR data with booking information
            qr_data = {
                'booking_number': booking_number,
                'booking_id': booking_id,
                'booking_status' : booking_status,
                'confirmation_code': confirmation_code,
                'merchant': merchant_name,
                'date': appointment_date,
                'time': appointment_time
            }
            
            # Create QR code with high error correction (allows 30% data recovery)
            qr = qrcode.QRCode(
                version=None,  # Auto determine version
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            
            # Encode the booking data in QR code
            qr.add_data(json.dumps(qr_data))
            qr.make(fit=True)
            
            # Create QR image with purple/lavender color (no logo)
            qr_img = qr.make_image(fill_color="#8b5cf6", back_color="white").convert("RGB")
            
            # Save QR code
            filename = f"booking_{booking_id}_{booking_number}.png"
            filepath = os.path.join(self.upload_dir, filename)
            qr_img.save(filepath, 'PNG', quality=95)
            
            # Return relative URL path
            return f"/static/uploads/qr_codes/{filename}"
            
        except Exception as e:
            print(f"Error generating QR code for booking {booking_id}: {str(e)}")
            return None
    
    def delete_qr_code(self, booking_id: int, booking_number: str) -> bool:
        """Delete a QR code file"""
        try:
            filename = f"booking_{booking_id}_{booking_number}.png"
            filepath = os.path.join(self.upload_dir, filename)
            
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
            return False
        except Exception as e:
            print(f"Error deleting QR code: {str(e)}")
            return False


# Create global instance
qr_generator = QRCodeGenerator()
