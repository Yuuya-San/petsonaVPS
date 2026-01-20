from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, IntegerField, FloatField, SelectField, SelectMultipleField, TimeField, BooleanField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Email, Length, NumberRange, URL, Optional, Regexp, ValidationError
from wtforms.widgets import CheckboxInput, ListWidget


class MultiCheckboxField(SelectMultipleField):
    """Custom field for multi-checkbox selection"""
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


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

    business_type = SelectField(
        'Business Type',
        choices=[
            ('', '-- Select Business Type --'),
            ('hotel', 'Pet Hotel'),
            ('boarding', 'Pet Boarding Facility'),
            ('grooming', 'Pet Grooming Salon'),
            ('vet', 'Veterinary Clinic'),
            ('trainer', 'Pet Training Center'),
            ('transport', 'Pet Transport Service'),
        ],
        validators=[DataRequired(message='Please select a business type')],
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

    years_in_operation = IntegerField(
        'Years in Operation (Optional)',
        validators=[
            Optional(),
            NumberRange(min=0, max=100, message='Please enter a valid number of years')
        ],
        render_kw={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800 placeholder-gray-400',
            'placeholder': 'e.g., 5',
            'type': 'number',
            'min': '0',
            'max': '100'
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
            Regexp(r'^\+?63\d{10}$|^09\d{9}$', message='Please provide a valid Philippine phone number (09XX-XXX-XXXX or +63...)')
        ],
        render_kw={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800 placeholder-gray-400',
            'placeholder': 'e.g., 09XX-XXX-XXXX or +639XX-XXX-XXXX',
        }
    )

    # ========== SECTION 3: LOCATION ==========
    province = SelectField(
        'Province',
        choices=[('', '-- Select Province --')],
        validators=[DataRequired(message='Please select a province')],
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
            Optional(),
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

    # ========== SECTION 4: SERVICES OFFERED ==========
    services_offered = MultiCheckboxField(
        'Services Offered',
        choices=[
            ('Pet Hotel', 'Pet Hotel (Overnight Stay)'),
            ('Pet Boarding', 'Pet Boarding (Daycare)'),
            ('Pet Grooming', 'Pet Grooming'),
            ('Pet Training', 'Pet Training'),
            ('Pet Transport', 'Pet Transport'),
            ('Veterinary Clinic', 'Veterinary Clinic'),
        ],
        validators=[DataRequired(message='Please select at least one service')],
        render_kw={'class': 'space-y-2'}
    )

    # ========== SECTION 5: PETS ACCEPTED ==========
    pets_accepted = MultiCheckboxField(
        'Pets Accepted',
        choices=[
            ('Dogs', 'Dogs'),
            ('Cats', 'Cats'),
            ('Birds', 'Birds'),
            ('Rabbits', 'Rabbits'),
            ('Reptiles', 'Reptiles'),
            ('Exotic Pets', 'Exotic Pets'),
        ],
        validators=[DataRequired(message='Please select at least one pet type')],
        render_kw={'class': 'space-y-2'}
    )

    # ========== SECTION 6: CAPACITY & PRICING ==========
    max_pets_per_day = IntegerField(
        'Maximum Pets Per Day',
        validators=[
            DataRequired(message='Capacity is required'),
            NumberRange(min=1, max=10000, message='Capacity must be between 1 and 10,000 pets')
        ],
        render_kw={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800 placeholder-gray-400',
            'placeholder': 'e.g., 50',
            'type': 'number',
            'min': '1'
        }
    )

    min_price_per_day = FloatField(
        'Minimum Price Per Day (₱)',
        validators=[
            DataRequired(message='Minimum price is required'),
            NumberRange(min=0, max=999999, message='Price must be a positive number')
        ],
        render_kw={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800 placeholder-gray-400',
            'placeholder': 'e.g., 500.00',
            'type': 'number',
            'min': '0',
            'step': '0.01'
        }
    )

    max_price_per_day = FloatField(
        'Maximum Price Per Day (₱)',
        validators=[
            DataRequired(message='Maximum price is required'),
            NumberRange(min=0, max=999999, message='Price must be a positive number')
        ],
        render_kw={
            'class': 'w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-purple-500 focus:outline-none transition-colors bg-white text-gray-800 placeholder-gray-400',
            'placeholder': 'e.g., 1500.00',
            'type': 'number',
            'min': '0',
            'step': '0.01'
        }
    )

    # ========== SECTION 7: OPERATING SCHEDULE ==========
    opening_time = StringField(
        'Opening Time',
        validators=[
            DataRequired(message='Opening time is required'),
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
            DataRequired(message='Closing time is required'),
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
        validators=[DataRequired(message='Please select at least one operating day')],
        render_kw={'class': 'space-y-2'}
    )

    # ========== SECTION 8: POLICIES ==========
    vaccination_required = BooleanField(
        'Vaccination Required',
        render_kw={'class': 'w-4 h-4 text-purple-600 rounded focus:ring-2 focus:ring-purple-500'}
    )

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
            DataRequired(message='Please upload at least 3 facility photos')
        ]
    )

    # ========== SUBMIT ==========
    submit = SubmitField(
        'Submit Application',
        render_kw={
            'class': 'w-full px-6 py-3 bg-gradient-to-r from-purple-500 to-purple-600 text-white font-semibold rounded-lg hover:from-purple-600 hover:to-purple-700 transition-all duration-300 transform hover:scale-105 shadow-lg'
        }
    )

    # ========== CUSTOM VALIDATORS ==========
    def validate_max_price_per_day(self, field):
        """Ensure max price is greater than or equal to min price"""
        if self.min_price_per_day.data and field.data:
            if field.data < self.min_price_per_day.data:
                raise ValidationError('Maximum price must be greater than or equal to minimum price')

    def validate_closing_time(self, field):
        """Ensure closing time is after opening time"""
        if self.opening_time.data and field.data:
            if field.data <= self.opening_time.data:
                raise ValidationError('Closing time must be after opening time')

    def validate_services_offered(self, field):
        """Ensure at least one service is selected"""
        if not field.data or len(field.data) == 0:
            raise ValidationError('Please select at least one service')

    def validate_pets_accepted(self, field):
        """Ensure at least one pet type is selected"""
        if not field.data or len(field.data) == 0:
            raise ValidationError('Please select at least one pet type')

    def validate_operating_days(self, field):
        """Ensure at least one operating day is selected"""
        if not field.data or len(field.data) == 0:
            raise ValidationError('Please select at least one operating day')
