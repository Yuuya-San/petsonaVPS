from flask import request
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, IntegerField, FloatField, SelectField, SelectMultipleField, TimeField, BooleanField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Email, Length, NumberRange, URL, Optional, Regexp, ValidationError
from wtforms.widgets import CheckboxInput, ListWidget
from wtforms.fields import Field
from werkzeug.datastructures import FileStorage

# ========== ALLOWED VALUES CONSTANTS ==========
ALLOWED_BUSINESS_CATEGORIES = [
    'Pet Hotel',
    'Pet Boarding',
    'Pet Daycare',
]

ALLOWED_SERVICES = [
    'Pet Hotel',
    'Pet Boarding',
    'Pet Daycare',
]

ALLOWED_PETS = [
    'Dogs',
    'Cats',
    'Small Mammals',
    'Birds',
    'Reptiles & Amphibians',
    'Aquatic Pets',
]


class MultiCheckboxField(SelectMultipleField):
    """Custom field for multi-checkbox selection"""
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class MultiFileField(Field):
    """Custom field for multiple file uploads"""
    def __init__(self, label=None, validators=None, **kwargs):
        super().__init__(label, validators, **kwargs)
        self.data = []

    def _value(self):
        return ''

    def process_formdata(self, valuelist):
        """Process form data from file input"""
        if valuelist:
            self.data = valuelist
        else:
            self.data = []

    def process_data(self, value):
        """Process object data"""
        if value:
            self.data = value if isinstance(value, list) else [value]
        else:
            self.data = []


class MerchantApplicationForm(FlaskForm):
    """Comprehensive merchant application form with all required sections"""

    # ========== SECTION 1: BUSINESS INFORMATION ==========
    business_name = StringField(
        'Business Name',
        validators=[
            DataRequired(message='Business name is required'),
            Length(min=3, max=255, message='Business name must be between 3 and 255 characters')
        ],
        render_kw={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800 placeholder-gray-400',
            'placeholder': 'e.g., Happy Paws Hotel & Boarding',
        }
    )

    business_category = SelectField(
        'Business Category',
        choices=[(cat, cat) for cat in ALLOWED_BUSINESS_CATEGORIES],
        validators=[DataRequired(message='Please select a business category')],
        render_kw={'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800'}
    )

    business_description = TextAreaField(
        'Business Description',
        validators=[
            DataRequired(message='Please provide a business description'),
            Length(min=20, max=1000, message='Description must be between 20 and 1000 characters')
        ],
        render_kw={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800 placeholder-gray-400 resize-vertical',
            'placeholder': 'Tell us about your business, specialties, and what makes you unique...',
            'rows': 5,
        }
    )

    # ========== SECTION 2: CONTACT PERSON ==========
    owner_manager_name = StringField(
        'Owner / Manager Full Name',
        validators=[
            DataRequired(message='Full name is required'),
            Length(min=3, max=128, message='Name must be between 3 and 128 characters')
        ],
        render_kw={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800 placeholder-gray-400',
            'placeholder': 'e.g., Juan Dela Cruz',
        }
    )

    contact_email = StringField(
        'Contact Email',
        validators=[
            DataRequired(message='Email is required'),
            Email(message='Please provide a valid email address')
        ],
        render_kw={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800 placeholder-gray-400',
            'placeholder': 'e.g., contact@happypaws.com',
            'type': 'email'
        }
    )

    contact_phone = StringField(
        'Contact Phone',
        validators=[
            DataRequired(message='Phone number is required'),
            Regexp(r'^\d{10}$', message='Phone number must be exactly 10 digits (Philippine format only)')
        ],
        render_kw={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800 placeholder-gray-400',
            'placeholder': '9XX-XXX-XXXX (10 digits)',
            'inputmode': 'numeric',
            'pattern': '[0-9]{10}',
            'maxlength': '10'
        }
    )

    # ========== SECTION 3: LOCATION ==========
    region = SelectField(
        'Region',
        choices=[('', '-- Select Region --')],
        validators=[DataRequired(message='Please select a region')],
        validate_choice=False,
        render_kw={'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800'}
    )

    province = SelectField(
        'Province',
        choices=[('', '-- Select Province --')],
        validators=[Optional()],
        validate_choice=False,
        render_kw={'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800'}
    )

    city = SelectField(
        'City / Municipality',
        choices=[('', '-- Select City/Municipality --')],
        validators=[DataRequired(message='Please select a city or municipality')],
        validate_choice=False,
        render_kw={'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800'}
    )

    barangay = SelectField(
        'Barangay (Optional)',
        choices=[('', '-- Select Barangay --')],
        validators=[Optional()],
        validate_choice=False,
        render_kw={'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800'}
    )

    postal_code = StringField(
        'Postal Code',
        validators=[
            Optional(),
            Length(min=4, max=4, message='Postal code must be exactly 4 digits'),
            Regexp(r'^\d{4}$', message='Postal code must contain only numbers')
        ],
        render_kw={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800 placeholder-gray-400',
            'placeholder': 'e.g., 1200',
            'inputmode': 'numeric',   
            'pattern': '[0-9]{4}',   
            'maxlength': '4',
            'minlength': '4'
        }
    )

    google_maps_link = StringField(
        'Google Maps Link (Optional)',
        validators=[
            DataRequired(message='Google Maps link is required'),
            URL(message='Please provide a valid Google Maps URL')
        ],
        render_kw={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800 placeholder-gray-400',
            'placeholder': 'e.g., https://maps.google.com/?q=...',
        }
    )

    full_address = StringField(
        'Full Address',
        validators=[DataRequired(message='Please pin your location on the map to get the full address')],
        render_kw={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800',
            'readonly': True,
        }
    )

    # Map coordinates (hidden fields)
    latitude = HiddenField('Latitude', validators=[Optional()])
    longitude = HiddenField('Longitude', validators=[Optional()])


    # ========== SECTION 5: PETS ACCEPTED ==========
    pets_accepted = MultiCheckboxField(
        'Pets Accepted',
        choices=[(pet, pet) for pet in ALLOWED_PETS],
        validators=[DataRequired(message='Please select at least one pet type')],
        render_kw={'class': 'space-y-2'}
    )


    # Hidden field for service pricing JSON structure
    service_pricing_json = HiddenField('Service Pricing', validators=[Optional()])

    # ========== SECTION 7: OPERATING SCHEDULE ==========
    is_24h = BooleanField(
        '24/7 Operation',
        validators=[Optional()],
        render_kw={'class': 'w-4 h-4 text-purple-600 rounded focus:ring-2 focus:ring-purple-500'}
    )

    opening_time = StringField(
        'Opening Time',
        validators=[
            Optional(),
            Regexp(r'^([01]\d|2[0-3]):([0-5]\d)$', message='Please use HH:MM format (24-hour)')
        ],
        render_kw={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800',
            'type': 'time',
        }
    )

    closing_time = StringField(
        'Closing Time',
        validators=[
            Optional(),
            Regexp(r'^([01]\d|2[0-3]):([0-5]\d)$', message='Please use HH:MM format (24-hour)')
        ],
        render_kw={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800',
            'type': 'time',
        }
    )

    operating_days = MultiCheckboxField(
        'Operating Days',
        choices=[
            ('Monday', 'Monday'),
            ('Tuesday', 'Tuesday'),
            ('Wednesday', 'Wednesday'),
            ('Thursday', 'Thursday'),
            ('Friday', 'Friday'),
            ('Saturday', 'Saturday'),
            ('Sunday', 'Sunday'),
        ],
        validators=[Optional()],
        render_kw={'class': 'space-y-2'}
    )

    # ========== SECTION 8: POLICIES ==========
    cancellation_policy = TextAreaField(
        'Cancellation Policy',
        validators=[
            Optional(),
            Length(max=1000, message='Cancellation policy must not exceed 1000 characters')
        ],
        render_kw={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800 placeholder-gray-400 resize-vertical',
            'placeholder': 'Describe your cancellation policy (e.g., Free cancellation up to 48 hours before service)...',
            'rows': 4,
        }
    )

    # ========== SECTION 9: VERIFICATION UPLOADS ==========
    store_logo = FileField(
        'Store Logo',
        validators=[
            DataRequired(message='Store logo is required'),
            FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], message='Only JPG, PNG, GIF, and WebP files are allowed')
        ],
        render_kw={'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-purple-100 file:text-purple-700 hover:file:bg-purple-200'}
    )

    government_id = FileField(
        'Government-Issued ID',
        validators=[
            DataRequired(message='Government-issued ID is required'),
            FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], message='Only JPG, PNG, and PDF files are allowed')
        ],
        render_kw={'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-purple-100 file:text-purple-700 hover:file:bg-purple-200'}
    )

    business_permit = FileField(
        'Business Permit / License',
        validators=[
            DataRequired(message='Business permit/license is required'),
            FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], message='Only JPG, PNG, and PDF files are allowed')
        ],
        render_kw={'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-purple-100 file:text-purple-700 hover:file:bg-purple-200'}
    )

    facility_photos = FileField(
        'Facility Photos (Minimum 3)',
        render_kw={
            'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-purple-100 file:text-purple-700 hover:file:bg-purple-200',
            'multiple': True,
            'accept': 'image/*'
        },
        validators=[
            Optional()  # Handle validation in route since this is a multi-file field
        ]
    )

    # ========== SUBMIT ==========
    agree_terms = BooleanField(
        'I agree to the terms and conditions',
        validators=[DataRequired(message='You must agree to the terms and conditions')],
        render_kw={'class': 'w-4 h-4 text-purple-600 rounded focus:ring-2 focus:ring-purple-500'}
    )

    submit = SubmitField(
        'Submit Application',
        render_kw={
            'class': 'w-full px-6 py-3 bg-gradient-to-r from-purple-500 to-purple-600 text-white font-semibold rounded-lg hover:from-purple-600 hover:to-purple-700 transition-all duration-300 transform hover:scale-105 shadow-lg'
        }
    )

    # ========== CUSTOM VALIDATORS ==========
    def validate_max_price(self, field):
        """Ensure max price is greater than or equal to min price"""
        if self.min_price.data and field.data:
            if field.data < self.min_price.data:
                raise ValidationError('Maximum price must be greater than or equal to minimum price')

    def validate_closing_time(self, field):
        """Ensure closing time is after opening time (only if both provided and Pet Daycare)"""
        # Only validate for Pet Daycare if operating times are provided
        if self.business_category.data == 'Pet Daycare':
            if self.opening_time.data and field.data:
                if field.data <= self.opening_time.data:
                    raise ValidationError('Closing time must be after opening time')

    def validate_pets_accepted(self, field):
        """Ensure at least one pet type is selected"""
        if not field.data or len(field.data) == 0:
            raise ValidationError('Please select at least one pet type')

    def validate_operating_days(self, field):
        """Ensure operating days are selected only for Pet Daycare"""
        # Only validate for Pet Daycare
        if self.business_category.data == 'Pet Daycare':
            if not field.data or len(field.data) == 0:
                raise ValidationError('Please select at least one operating day')

    def validate_province(self, field):
        """Require province unless NCR / Metro Manila is selected."""
        region_value = self.region.data if hasattr(self, 'region') else ''
        if region_value and str(region_value).strip().upper().startswith('NCR'):
            return
        if not field.data or not str(field.data).strip():
            raise ValidationError('Please select a province')

class MerchantStoreUpdateForm(FlaskForm):
    """Form for updating merchant store information - mirrors MerchantApplicationForm for editing"""

    business_category = SelectField(
        'Business Category',
        choices=[(cat, cat) for cat in ALLOWED_BUSINESS_CATEGORIES],
        validators=[DataRequired(message='Please select a business category')],
        render_kw={'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800'}
    )

    # ========== SECTION 1: BUSINESS INFORMATION ==========
    business_name = StringField(
        'Business Name',
        validators=[
            DataRequired(message='Business name is required'),
            Length(min=3, max=255, message='Business name must be between 3 and 255 characters')
        ],
        render_kw={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all bg-white text-slate-900 text-sm',
            'placeholder': 'e.g., Happy Paws Hotel & Boarding',
        }
    )

    business_category = SelectField(
        'Business Category',
        choices=[(cat, cat) for cat in ALLOWED_BUSINESS_CATEGORIES],
        validators=[DataRequired(message='Please select a business category')],
        render_kw={'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all bg-white text-slate-900 text-sm'}
    )

    business_description = TextAreaField(
        'Business Description',
        validators=[
            DataRequired(message='Please provide a business description'),
            Length(min=20, max=1000, message='Description must be between 20 and 1000 characters')
        ],
        render_kw={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all bg-white text-slate-900 text-sm resize-vertical',
            'placeholder': 'Tell us about your business, specialties, and what makes you unique...',
            'rows': 4,
        }
    )


    owner_manager_name = StringField(
        'Owner / Manager Full Name',
        validators=[
            DataRequired(message='Full name is required'),
            Length(min=3, max=128, message='Name must be between 3 and 128 characters')
        ],
        render_kw={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all bg-white text-slate-900 text-sm',
            'placeholder': 'e.g., Juan Dela Cruz',
        }
    )

    contact_email = StringField(
        'Contact Email',
        validators=[
            DataRequired(message='Email is required'),
            Email(message='Please provide a valid email address')
        ],
        render_kw={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all bg-white text-slate-900 text-sm',
            'placeholder': 'e.g., contact@happypaws.com',
            'type': 'email'
        }
    )

    contact_phone = StringField(
        'Contact Phone',
        validators=[
            DataRequired(message='Phone number is required'),
            Regexp(r'^\d{10}$', message='Phone number must be exactly 10 digits (Philippine format only)')
        ],
        render_kw={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all bg-white text-slate-900 text-sm',
            'placeholder': '9XX-XXX-XXXX (10 digits)',
            'inputmode': 'numeric',
            'pattern': '[0-9]{10}',
            'maxlength': '10'
        }
    )

    # ========== SECTION 3: LOCATION ==========
    region = SelectField(
        'Region',
        choices=[('', '-- Select Region --')],
        validators=[DataRequired(message='Please select a region')],
        validate_choice=False,
        render_kw={'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all bg-white text-slate-900 text-sm'}
    )

    province = SelectField(
        'Province',
        choices=[('', '-- Select Province --')],
        filters=[lambda x: x if x else request.form.get('province_fallback')],
        validators=[Optional()],
        validate_choice=False,
        render_kw={'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all bg-white text-slate-900 text-sm'}
    )

    city = SelectField(
        'City / Municipality',
        choices=[('', '-- Select City/Municipality --')],
        filters=[lambda x: x if x else request.form.get('city_fallback')],
        validators=[DataRequired(message='Please select a city or municipality')],
        validate_choice=False,
        render_kw={'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all bg-white text-slate-900 text-sm'}
    )

    barangay = SelectField(
        'Barangay (Optional)',
        choices=[('', '-- Select Barangay --')],
        filters=[lambda x: x if x else request.form.get('barangay_fallback')],
        validators=[Optional()],
        validate_choice=False,
        render_kw={'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all bg-white text-slate-900 text-sm'}
    )

    postal_code = StringField(
        'Postal Code',
        validators=[
            Optional(),
            Length(min=4, max=4, message='Postal code must be exactly 4 digits'),
            Regexp(r'^\d{4}$', message='Postal code must contain only numbers')
        ],
        render_kw={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all bg-white text-slate-900 text-sm',
            'placeholder': 'e.g., 1200',
            'inputmode': 'numeric',   
            'pattern': '[0-9]{4}',   
            'maxlength': '4',
            'minlength': '4'
        }
    )

    google_maps_link = StringField(
        'Google Maps Link (Optional)',
        validators=[
            DataRequired(message='Google Maps link is required'),
            URL(message='Please provide a valid Google Maps URL')
        ],
        render_kw={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all bg-white text-slate-900 text-sm',
            'placeholder': 'e.g., https://maps.google.com/?q=...',
        }
    )

    full_address = StringField(
        'Full Address',
        validators=[DataRequired(message='Please pin your location on the map to get the full address')],
        render_kw={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all bg-white text-slate-900 text-sm',
            'readonly': True,
        }
    )

    # Map coordinates (hidden fields)
    latitude = HiddenField('Latitude', validators=[Optional()])
    longitude = HiddenField('Longitude', validators=[Optional()])


    # ========== SECTION 5: PETS ACCEPTED ==========
    pets_accepted = MultiCheckboxField(
        'Pets Accepted',
        choices=[(pet, pet) for pet in ALLOWED_PETS],
        validators=[DataRequired(message='Please select at least one pet type')],
        render_kw={'class': 'space-y-2'}
    )



    # Hidden field for service pricing JSON structure
    service_pricing_json = HiddenField('Service Pricing', validators=[Optional()])

    # ========== SECTION 7: OPERATING SCHEDULE ==========
    is_24h = BooleanField(
        '24/7 Operation',
        validators=[Optional()],
        render_kw={'class': 'w-4 h-4 text-purple-600 rounded focus:ring-2 focus:ring-purple-500'}
    )

    opening_time = StringField(
        'Opening Time',
        validators=[
            Optional(),
            Regexp(r'^([01]\d|2[0-3]):([0-5]\d)$', message='Please use HH:MM format (24-hour)')
        ],
        render_kw={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all bg-white text-slate-900 text-sm',
            'type': 'time',
        }
    )

    closing_time = StringField(
        'Closing Time',
        validators=[
            Optional(),
            Regexp(r'^([01]\d|2[0-3]):([0-5]\d)$', message='Please use HH:MM format (24-hour)')
        ],
        render_kw={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all bg-white text-slate-900 text-sm',
            'type': 'time',
        }
    )

    operating_days = MultiCheckboxField(
        'Operating Days',
        choices=[
            ('Monday', 'Monday'),
            ('Tuesday', 'Tuesday'),
            ('Wednesday', 'Wednesday'),
            ('Thursday', 'Thursday'),
            ('Friday', 'Friday'),
            ('Saturday', 'Saturday'),
            ('Sunday', 'Sunday'),
        ],
        validators=[Optional()],
        render_kw={'class': 'space-y-2'}
    )

    # ========== SECTION 8: POLICIES ==========
    cancellation_policy = TextAreaField(
        'Cancellation Policy',
        validators=[
            Optional(),
            Length(max=1000, message='Cancellation policy must not exceed 1000 characters')
        ],
        render_kw={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all bg-white text-slate-900 text-sm resize-vertical',
            'placeholder': 'Describe your cancellation policy (e.g., Free cancellation up to 48 hours before service)...',
            'rows': 4,
        }
    )

    # ========== SECTION 8: FILE UPLOADS ==========
    store_logo = FileField(
        'Store Logo',
        validators=[
            Optional(),
            FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], message='Only JPG, PNG, GIF, and WebP files are allowed')
        ]
    )

    government_id = FileField(
        'Government ID',
        validators=[
            Optional(),
            FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], message='Only JPG, PNG, and PDF files are allowed')
        ]
    )

    business_permit = FileField(
        'Business Permit/License',
        validators=[
            Optional(),
            FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], message='Only JPG, PNG, and PDF files are allowed')
        ]
    )

    facility_photos = MultiFileField(
        'Facility Photos',
        validators=[
            Optional(),
            FileAllowed(['jpg', 'jpeg', 'png'], message='Only JPG and PNG files are allowed')
        ]
    )

    # ========== SUBMIT ==========
    submit = SubmitField(
        'Save Changes',
        render_kw={
            'class': 'w-full px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition-all duration-300 shadow-md'
        }
    )

    # ========== CUSTOM VALIDATORS ==========
    def validate_max_price(self, field):
        """Ensure max price is greater than or equal to min price"""
        if self.min_price.data and field.data:
            if field.data < self.min_price.data:
                raise ValidationError('Maximum price must be greater than or equal to minimum price')

    def validate_closing_time(self, field):
        """Ensure closing time is after opening time (only if both provided and Pet Daycare)"""
        # Only validate for Pet Daycare if operating times are provided
        if self.business_category.data == 'Pet Daycare':
            if self.opening_time.data and field.data:
                if field.data <= self.opening_time.data:
                    raise ValidationError('Closing time must be after opening time')

    def validate_pets_accepted(self, field):
        """Ensure at least one pet type is selected"""
        if not field.data or len(field.data) == 0:
            raise ValidationError('Please select at least one pet type')

    def validate_operating_days(self, field):
        """Ensure operating days are selected only for Pet Daycare"""
        # Only validate for Pet Daycare
        if self.business_category.data == 'Pet Daycare':
            if not field.data or len(field.data) == 0:
                raise ValidationError('Please select at least one operating day')

    def validate_province(self, field):
        """Require province unless NCR / Metro Manila is selected."""
        region_value = self.region.data if hasattr(self, 'region') else ''
        if region_value and str(region_value).strip().upper().startswith('NCR'):
            return
        if not field.data or not str(field.data).strip():
            raise ValidationError('Please select a province')