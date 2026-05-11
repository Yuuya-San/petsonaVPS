"""Forms for messaging."""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, ValidationError


class SendMessageForm(FlaskForm):
    """Form for sending a message."""
    content = TextAreaField(
        'Message',
        validators=[DataRequired(), Length(min=1, max=5000)]
    )
    submit = SubmitField('Send')


class ReportMessageForm(FlaskForm):
    """Form for reporting a message."""
    reason = SelectField(
        'Reason for Report',
        choices=[
            ('spam', 'Spam or Harassment'),
            ('inappropriate', 'Inappropriate Content'),
            ('abuse', 'Abusive Language'),
            ('threat', 'Threats or Violence'),
            ('fake', 'Impersonation or Fake Account'),
            ('scam', 'Scam or Fraud'),
            ('other', 'Other'),
        ],
        validators=[DataRequired()]
    )
    details = TextAreaField(
        'Additional Details',
        validators=[Length(max=500)]
    )
    submit = SubmitField('Report')


class BlockUserForm(FlaskForm):
    """Form for blocking a user."""
    reason = SelectField(
        'Reason for Blocking',
        choices=[
            ('spam', 'Spam or Harassment'),
            ('inappropriate', 'Inappropriate Content'),
            ('abuse', 'Abusive Language'),
            ('threat', 'Threats or Violence'),
            ('personal', 'Personal Preference'),
            ('other', 'Other'),
        ],
        validators=[DataRequired()]
    )
    submit = SubmitField('Block User')
