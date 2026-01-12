from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('library', '0001_initial'),
    ]

    operations = [
        # 1. Add Thumbnail and Order to KnowledgeNode
        migrations.AddField(
            model_name='knowledgenode',
            name='thumbnail_url',
            field=models.URLField(blank=True, help_text='Image URL for the card', null=True),
        ),
        migrations.AddField(
            model_name='knowledgenode',
            name='order',
            field=models.PositiveIntegerField(default=0),
        ),
        
        # 2. Add Order to Resource
        migrations.AddField(
            model_name='resource',
            name='order',
            field=models.PositiveIntegerField(default=0),
        ),

        # 3. Create the StudentProgress Table
        migrations.CreateModel(
            name='StudentProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_completed', models.BooleanField(default=False)),
                ('last_accessed', models.DateTimeField(auto_now=True)),
                ('resource', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='progress_records', to='library.resource')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='progress', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'resource')},
            },
        ),
    ]
