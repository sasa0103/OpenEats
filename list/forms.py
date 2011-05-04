from django.forms import ModelForm, forms
import django.forms as forms
from django.http import HttpResponse
from models import GroceryList,GroceryShared
from django.forms.models import BaseInlineFormSet
from django.utils.translation import ugettext_lazy as _
from django.core.mail import EmailMessage, BadHeaderError
from django.conf import settings
from django.template import loader, RequestContext
from django.contrib.sites.models import Site

class GroceryListForm(ModelForm):
    '''used to create a new grocery list for a user'''
    class Meta:
        model = GroceryList
        exclude=('slug')

class GroceryItemFormSet(BaseInlineFormSet):
     """Require at least one form in the formset to be completed."""
     def clean(self):
         super(GroceryItemFormSet, self).clean()
         for error in self.errors:
             if error:
                 return
         completed = 0
         for cleaned_data in self.cleaned_data:
             if cleaned_data and not cleaned_data.get('DELETE', False):
                 completed += 1
         if completed < 1:
             raise forms.ValidationError("At least one %s is required." %
                self.model._meta.object_name.lower())



class GroceryUserList(forms.Form):
    '''used to pull a list of a users grocery list and add them to a select box on a form'''
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None) #get the user passed to the form off of the keyword argument
        super(GroceryUserList, self).__init__(*args, **kwargs)
        lists = GroceryList.objects.filter(author=user)
        choices=[ (o.id, str(o)) for o in lists]
        choices.append((0,'new'))
        choices.sort()
        self.fields['lists'] = forms.ChoiceField( widget = forms.Select(), choices=choices, initial=0)


class GroceryShareTo(forms.Form):
    '''grocery form to allow you to select a user from your friends to share a list with'''
    def __init__(self, data=None, files=None, request=None, *args, **kwargs):
        if request is None:
            raise TypeError("Keyword argument 'request must be supplies'")
        super(GroceryShareTo, self).__init__(data=data, files=files, *args, **kwargs)
        self.request = request
        friends = self.request.relationships.friends()
        choices=[ (o.id, str(o)) for o in friends]
        choices.sort()
        self.fields['share_to'] = forms.ChoiceField( widget= forms.Select(), choices=choices, required=True)

    def save(self):
        list = self.request['list']
        new_share = GroceryShared()
        new_share.list = list
        new_share.shared_to = self.request['shared_to']
        new_share.shared_by = request.user
        new_share.save()

    
class GrocerySendMail(forms.Form):
    '''Grocery form to send a grocery list to someone in email'''
    def __init__(self, data=None, files=None, request=None, *args, **kwargs):
        if request is None:
            raise TypeError("Keyword argument 'request must be supplies'")
        super(GrocerySendMail, self).__init__(data=data, files=files, *args, **kwargs)
        self.request = request
        #set up the return email address and sender name to the user logged in
        if request.user.is_authenticated():
            self.fields['to_email'].initial= request.user.email
            

    to_email = forms.EmailField(widget=forms.TextInput(),label=_('email address'))
    gid = forms.CharField(widget=forms.HiddenInput())

    from_email = settings.DEFAULT_FROM_EMAIL
    from_site = Site.objects.get_current()
    subject = _('Grocery list from ' + str(from_site))


    def get_body(self):
        '''get the grocery list and return the message body for the email'''
        if self.is_valid():
            list = GroceryList.objects.get(pk = self.cleaned_data['gid'])
            template_name = 'list/grocery_mail_body.html' #template that contains the email body and also shared by the grocery print view
            message = loader.render_to_string(template_name, {'list': list}, context_instance=RequestContext(self.request))
            return message
        else:
            raise ValueError(_('Can not get grocery list id from invalid form data'))

    def get_toMail(self):
        '''gets the email to send the list to from the form'''
        if self.is_valid():
            return self.cleaned_data['to_email']
        else:
            raise ValueError(_('Can not get to_email from invalid form data'))

    def save(self, fail_silently=False):
        ''' sends the email message'''
        if self.subject and self.get_body() and self.from_email:
            try:
                msg = EmailMessage(self.subject, self.get_body(), self.from_email, [self.get_toMail()])
                msg.content_subtype = 'html'
                msg.send()
            except BadHeaderError:
                return HttpResponse(_('Invalid header found.'))
            return HttpResponse(_('Email Sent'))
        else:
         return HttpResponse('Make sure all fields are entered and valid.')



        

    
