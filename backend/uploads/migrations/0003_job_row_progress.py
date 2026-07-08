from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("uploads", "0002_uploadedfile_saved_filename"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="rows_processed",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="job",
            name="total_rows",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
