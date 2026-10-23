from django.core.exceptions import ValidationError
from django.db import models

class Event(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    location = models.CharField(max_length=200)
    saved_location = models.ForeignKey('Place', on_delete=models.CASCADE, null=True, blank=True)
    email_organizer = models.EmailField(max_length=200, blank=True, null=True)
    facebook_link = models.URLField(max_length=200, blank=True, null=True)
    form_link = models.URLField(max_length=200, blank=True, null=True)
    category = models.ForeignKey('Category', on_delete=models.CASCADE)
    organizer = models.CharField(max_length=200, default="Non renseigné")
    pmr_friendly = models.BooleanField(default=False)
    deaf_friendly = models.BooleanField(default=False)
    blind_friendly = models.BooleanField(default=False)
    neurodiversity_friendly = models.BooleanField(default=False)
    granz_filled = models.BooleanField(default=False)
    granz_validated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    validated = models.BooleanField(default=False)

    def __str__(self):
        return self.title

class EventDates(models.Model):
    start = models.DateTimeField()
    end = models.DateTimeField()
    event = models.ForeignKey(Event, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.start) + " - " + str(self.end)

class Category(models.Model):
    name = models.CharField(max_length=50)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    description = models.TextField()

    def __str__(self):
        return self.name

class Place(models.Model):
    name = models.CharField(max_length=200)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    address = models.CharField(max_length=200, blank=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    def __str__(self):
        return self.name

class AcademicPeriod(models.Model):
    # A labelled range of weeks in the UCLouvain calendar, shown as the calendar's week number
    name = models.CharField(max_length=50, help_text='Label shown for each week, e.g. "S", "Blocus", "Examens", "Congé"')
    start = models.DateField(help_text="Monday of the first week")
    end = models.DateField(help_text="Last day of the last week")
    numbered = models.BooleanField(default=False, help_text='Append a week number to the name ("S" becomes "S1", "S2", ...)')
    first_week_number = models.PositiveSmallIntegerField(default=1, help_text="Number of the first week when numbered")

    class Meta:
        ordering = ['start']

    def clean(self):
        if self.start and self.end and self.start > self.end:
            raise ValidationError("End date must be after start date")

    def __str__(self):
        return f"{self.name} ({self.start} - {self.end})"
