from django.db import models

class Medicine(models.Model):
    CATEGORY_CHOICES = (
        ('Antibiotics', 'Antibiotics'),
        ('Analgesics & Pain Relief', 'Analgesics & Pain Relief'),
        ('Antipyretic', 'Antipyretic (Fever)'),
        ('Antidiabetic', 'Antidiabetic'),
        ('Cardiovascular', 'Cardiovascular (Heart & BP)'),
        ('Respiratory & Anti-Allergic', 'Respiratory & Anti-Allergic'),
        ('Gastrointestinal', 'Gastrointestinal & Antacids'),
        ('Dermatology', 'Dermatology & Skin Care'),
        ('Vitamins & Supplements', 'Vitamins & Supplements'),
        ('Neurology & Psychiatry', 'Neurology & Psychiatry'),
        ('Other', 'Other Healthcare Products'),
    )

    DOSAGE_FORM_CHOICES = (
        ('Tablet', 'Tablet'),
        ('Capsule', 'Capsule'),
        ('Syrup', 'Syrup / Liquid Suspension'),
        ('Injection', 'Injection / Vial'),
        ('Ointment', 'Ointment / Cream / Gel'),
        ('Drops', 'Eye / Ear / Nasal Drops'),
        ('Inhaler', 'Inhaler / Respirator Solution'),
        ('Powder', 'Powder / Granules'),
    )

    medicine_name = models.CharField(
        max_length=200,
        db_index=True,
        verbose_name="Brand / Medicine Name"
    )
    generic_name = models.CharField(
        max_length=200,
        db_index=True,
        verbose_name="Generic / Chemical Name"
    )
    strength = models.CharField(
        max_length=100,
        help_text="e.g. 500mg, 10ml, 250mcg, 1g"
    )
    dosage_form = models.CharField(
        max_length=100,
        choices=DOSAGE_FORM_CHOICES,
        default='Tablet',
        db_index=True
    )
    category = models.CharField(
        max_length=100,
        choices=CATEGORY_CHOICES,
        db_index=True,
        default='Other'
    )
    description = models.TextField(blank=True, help_text="Therapeutic purpose or instructions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Medicine"
        verbose_name_plural = "Medicines"
        ordering = ['medicine_name']
        indexes = [
            models.Index(fields=['category', 'medicine_name'], name='med_cat_name_idx'),
            models.Index(fields=['dosage_form', 'category'], name='med_dosage_cat_idx'),
        ]

    def __str__(self):
        return f"{self.medicine_name} ({self.strength}) - {self.dosage_form}"
