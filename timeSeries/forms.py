import datetime as dt
from django import forms
from .models import Value, Series, Forecast


class UploadForm(forms.ModelForm):
    Series = forms.ModelChoiceField(queryset=Series.objects.all(), empty_label="(Select series)", to_field_name='name', label='',
                                    widget=forms.Select(attrs={'onchange':'getSeriesInfo();'}))
    
    class Meta:
        model = Series
        fields = ()
        
class ViewForm(forms.ModelForm):
    dateIni = forms.DateField(label='Start date', initial=dt.date.today)
    dateEnd = forms.DateField(label='End date', initial=dt.date.today)

    class Meta:
        model = Value
        exclude = ['date', 'record']
        
class ForecastForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super(ForecastForm, self).clean()
        raise forms.ValidationError(
                    "Did not send for 'help' in the subject despite "
                    "CC'ing yourself."
                )

    class Meta:
        model = Forecast
        exclude = [];

