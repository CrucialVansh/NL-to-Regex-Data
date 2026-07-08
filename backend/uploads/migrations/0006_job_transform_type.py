from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("uploads", "0005_alter_job_id_alter_uploadedfile_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="find_value",
            field=models.CharField(blank=True, max_length=1024),
        ),
        migrations.AddField(
            model_name="job",
            name="transform_type",
            field=models.CharField(
                choices=[
                    ("REGEX_REPLACE", "Regex replace"),
                    ("LITERAL_REPLACE", "Literal replace"),
                ],
                default="REGEX_REPLACE",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="job",
            name="replacement_value",
            field=models.CharField(blank=True, max_length=1024),
        ),
    ]
