from django import forms
from django.utils.translation import ugettext as _
from itertools import chain

import editors
from django.utils.safestring import mark_safe
from wiki import models
from django.forms.util import flatatt
from django.utils.encoding import force_unicode
from django.utils.html import escape, conditional_escape
from wiki.core.diff import simple_merge

class CreateRoot(forms.Form):
    
    title = forms.CharField(label=_(u'Title'), help_text=_(u'Initial title of the article. May be overridden with revision titles.'))
    content = forms.CharField(label=_(u'Type in some contents'),
                              help_text=_(u'This is just the initial contents of your article. After creating it, you can use more complex features like adding plugins, meta data, related articles etc...'),
                              required=False, widget=editors.editor.get_widget())
    

class EditForm(forms.Form):
    
    title = forms.CharField(label=_(u'Title'),)
    content = forms.CharField(label=_(u'Contents'),
                              required=False, widget=editors.editor.get_widget())
    
    summary = forms.CharField(label=_(u'Summary'), help_text=_(u'Give a short reason for your edit, which will be stated in the revision log.'),
                              required=False)
    
    current_revision = forms.IntegerField(required=False, widget=forms.HiddenInput())
    
    def __init__(self, current_revision, *args, **kwargs):
        
        self.preview = kwargs.pop('preview', False)
        self.initial_revision = current_revision
        self.presumed_revision = None
        if current_revision:
            initial = {'content': current_revision.content,
                       'title': current_revision.title,
                       'current_revision': current_revision.id}
            initial.update(kwargs.get('initial', {}))
            
            # Manipulate any data put in args[0] such that the current_revision
            # is reset to match the actual current revision.
            data = None
            if len(args) > 0:
                data = args[0]
            if not data:
                data = kwargs.get('data', None)
            if data:
                self.presumed_revision = data.get('current_revision', None)
                print self.initial_revision.id, self.presumed_revision
                if not str(self.presumed_revision) == str(self.initial_revision.id):
                    newdata = {}
                    for k,v in data.items():
                        newdata[k] = v
                    newdata['current_revision'] = self.initial_revision.id
                    newdata['content'] = simple_merge(self.initial_revision.content,
                                                      data.get('content', ""))
                    kwargs['data'] = newdata
                
            kwargs['initial'] = initial
        
        super(EditForm, self).__init__(*args, **kwargs)
    
    def clean(self):
        cd = self.cleaned_data
        if not str(self.initial_revision.id) == str(self.presumed_revision):
            raise forms.ValidationError(_(u'While you were editing, someone else changed the revision. Your contents have been automatically merged with the new contents. Please review the text below.'))
        if cd['title'] == self.initial_revision.title and cd['content'] == self.initial_revision.content:
            raise forms.ValidationError(_(u'No changes made. Nothing to save.'))
        return cd

class SelectWidgetBootstrap(forms.Select):
    """
    http://twitter.github.com/bootstrap/components.html#buttonDropdowns
    Needs bootstrap and jquery
    """
    js = ("""
    <script type="text/javascript">
        function setBtnGroupVal(elem) {
            selected_a = $(elem).parentsUntil('ul').find('a[selected]');
            if (selected_a.length > 0) {
                val = $(elem).parentsUntil('ul').find('a[selected]').attr('data-value');
                label = $(elem).parentsUntil('ul').find('a[selected]').html();
            } else {
                $(elem).parentsUntil('ul').find('a').first().attr('selected', 'selected');
                setBtnGroupVal(elem);
            }
            $(elem).val(val);
            $(elem).parents('.btn-group').find('.btn-group-label').html(label);
        }
        $(document).ready(function() {
            $('.btn-group-form input').each(function() {
                setBtnGroupVal(this);
            });
            $('.btn-group-form li a').click(function() {
                $(this).parent().siblings().find('a').attr('selected', '');
                $(this).attr('selected', 'selected');
                setBtnGroupVal(this);
            });
        })
    </script>
    """)
    def __init__(self, attrs={'class': 'btn-group pull-left btn-group-form'}, choices=()):
        self.noscript_widget = forms.Select(attrs={}, choices=choices)
        super(SelectWidgetBootstrap, self).__init__(attrs, choices)
    
    def __setattr__(self, k, value):
        super(SelectWidgetBootstrap, self).__setattr__(k, value)
        if k != 'attrs':
            self.noscript_widget.__setattr__(k, value)
    
    def render(self, name, value, attrs=None, choices=()):
        if value is None: value = ''
        final_attrs = self.build_attrs(attrs, name=name)
        output = ["""<div%(attrs)s>"""
                  """    <button class="btn btn-group-label" type="button">%(label)s</button>"""
                  """    <button class="btn dropdown-toggle" type="button" data-toggle="dropdown">"""
                  """        <span class="caret"></span>"""
                  """    </button>"""
                  """    <ul class="dropdown-menu">"""
                  """        %(options)s"""
                  """    </ul>"""
                  """    <input type="hidden" name="%(name)s" value="" class="btn-group-value" />"""
                  """</div>"""
                  """%(js)s"""
                  """<noscript>%(noscript)s</noscript>"""
                   % {'attrs': flatatt(final_attrs),
                      'options':self.render_options(choices, [value]),
                      'label': _(u'Select an option'),
                      'name': name,
                      'js': SelectWidgetBootstrap.js,
                      'noscript': self.noscript_widget.render(name, value, {}, choices)} ]
        return mark_safe(u'\n'.join(output))

    def render_option(self, selected_choices, option_value, option_label):
        option_value = force_unicode(option_value)
        selected_html = (option_value in selected_choices) and u' selected="selected"' or ''
        return u'<li><a href="#" data-value="%s"%s>%s</a></li>' % (
            escape(option_value), selected_html,
            conditional_escape(force_unicode(option_label)))

    def render_options(self, choices, selected_choices):
        # Normalize to strings.
        selected_choices = set([force_unicode(v) for v in selected_choices])
        output = []
        for option_value, option_label in chain(self.choices, choices):
            if isinstance(option_label, (list, tuple)):
                output.append(u'<li class="divider" label="%s"></li>' % escape(force_unicode(option_value)))
                for option in option_label:
                    output.append(self.render_option(selected_choices, *option))
            else:
                output.append(self.render_option(selected_choices, option_value, option_label))
        return u'\n'.join(output)
    

class TextInputPrepend(forms.TextInput):
    
    def __init__(self, *args, **kwargs):
        self.prepend = kwargs.pop('prepend', "")
        super(TextInputPrepend, self).__init__(*args, **kwargs)
    
    def render(self, *args, **kwargs):
        html = super(TextInputPrepend, self).render(*args, **kwargs)
        return mark_safe('<div class="input-prepend"><span class="add-on">%s</span>%s</div>' % (self.prepend, html))
    
class CreateForm(forms.Form):
    
    def __init__(self, urlpath_parent, *args, **kwargs):
        super(CreateForm, self).__init__(*args, **kwargs)
        # Todo: Don't change the widget in the default form, do it in
        # a class based view...
        self.fields['slug'].widget = TextInputPrepend(prepend='/'+urlpath_parent.path)
        self.urlpath_parent = urlpath_parent
    
    title = forms.CharField(label=_(u'Title'),)
    slug = forms.SlugField(label=_(u'Slug'), help_text=_(u"This will be the address where your article can be found. Use only alphanumeric characters and '-' or '_'."),)
    content = forms.CharField(label=_(u'Contents'),
                              required=False, widget=editors.editor.get_widget())
    
    summary = forms.CharField(label=_(u'Summary'), help_text=_(u"Write a brief message for the article's history log."),
                              required=False)
    
    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if slug[0] == "_":
            raise forms.ValidationError(_(u'A slug may not begin with an underscore.'))
        if models.URLPath.objects.filter(slug=slug, parent=self.urlpath_parent):
            raise forms.ValidationError(_(u'A slug named "%s" already exists.') % slug)
        return slug

class PermissionsForm(forms.ModelForm):
    
    settings_form_id = "perms"
    settings_form_headline = _(u'Permissions')
    settings_order = 5
    settings_write_access = False

    group = forms.ModelChoiceField(models.Group.objects.all(), widget=SelectWidgetBootstrap(),
                                   empty_label=_(u'(none)'), required=False)
    
    def __init__(self, article, *args, **kwargs):
        return super(PermissionsForm, self).__init__(*args, **kwargs)
    
    class Meta:
        model = models.Article
        fields = ('group', 'group_read', 'group_write', 'other_read', 'other_write')
