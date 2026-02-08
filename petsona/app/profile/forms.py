"""Profile forms for editing user information and avatar."""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Optional
import os

# Default avatars available for selection
DEFAULT_AVATARS = [
    "images/avatar/avatar-1.png",
    "images/avatar/avatar-2.png",
    "images/avatar/avatar-3.png",
    "images/avatar/avatar-4.png",
    "images/avatar/avatar-5.png",
    "images/avatar/avatar-6.png",
    "images/avatar/avatar-7.png",
    "images/avatar/avatar-8.png",
    "images/avatar/avatar-9.png",
    "images/avatar/avatar-10.png",
    "images/avatar/avatar-11.png",
    "images/avatar/avatar-12.png",
    "images/avatar/avatar-13.png",
    "images/avatar/avatar-14.png",
    "images/avatar/avatar-15.png",
    "images/avatar/avatar-16.png",
]


class ProfileForm(FlaskForm):
    """Form for editing user profile information."""
    
    first_name = StringField(
        'First Name',
        validators=[
            DataRequired(message='First name is required'),
            Length(min=2, max=64, message='First name must be between 2 and 64 characters')
        ]
    )
    
    last_name = StringField(
        'Last Name',
        validators=[
            DataRequired(message='Last name is required'),
            Length(min=2, max=64, message='Last name must be between 2 and 64 characters')
        ]
    )
    
    # Avatar selection: either upload new or choose from existing
    avatar_choice = SelectField(
        'Choose Default Avatar',
        choices=[(avatar, avatar.split('/')[-1].replace('.png', '').title()) for avatar in DEFAULT_AVATARS],
        validators=[Optional()]
    )
    
    # File upload for custom avatar
    avatar_upload = FileField(
        'Or Upload Custom Avatar',
        validators=[
            FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only (jpg, jpeg, png, gif)')
        ]
    )
    
    submit = SubmitField('Save Profile')
