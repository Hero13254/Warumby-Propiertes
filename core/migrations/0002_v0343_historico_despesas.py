from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='morador',
            name='anonimizado_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='PagamentoContaImovel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('competencia', models.DateField(help_text='Use o primeiro dia do mês de referência da conta.')),
                ('valor_pago', models.DecimalField(decimal_places=2, max_digits=12)),
                ('data_pagamento', models.DateField()),
                ('comprovante', models.FileField(blank=True, upload_to='contas/comprovantes/%Y/%m/')),
                ('observacoes', models.TextField(blank=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('conta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pagamentos', to='core.contaimovel')),
                ('criado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pagamentos_contas_criados', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Pagamento de conta do imóvel',
                'verbose_name_plural': 'Pagamentos de contas dos imóveis',
                'ordering': ['-competencia', '-data_pagamento', '-criado_em'],
            },
        ),
    ]