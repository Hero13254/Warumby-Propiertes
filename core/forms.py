import calendar
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django import forms
from django.db.models import Q, Sum
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .auth_utils import normalizar_cpf
from .models import (
    AjusteCompetencia,
    AnexoManutencao,
    Apartamento,
    Comunicado,
    ComprovantePagamento,
    ContaImovel,
    DocumentoMorador,
    MembroOcupacao,
    Morador,
    Ocupacao,
    Pagamento,
    PagamentoContaImovel,
    LancamentoPagamento,
    PerfilUsuario,
    Predio,
    SolicitacaoManutencao,
)


ARQUIVOS_IMAGEM_PDF_EXTENSOES = {'.pdf', '.png', '.jpg', '.jpeg', '.jfif', '.webp', '.heic', '.heif', '.avif'}
ARQUIVOS_IMAGEM_PDF_ACCEPT = 'image/*,.pdf,application/pdf'


def adicionar_meses(valor, meses):
    """Soma meses a uma data preservando o dia quando ele existe no mês destino."""
    total = valor.year * 12 + (valor.month - 1) + meses
    ano, mes_zero = divmod(total, 12)
    mes = mes_zero + 1
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, min(valor.day, ultimo_dia))


def subtrair_anos(valor, anos):
    try:
        return valor.replace(year=valor.year - anos)
    except ValueError:
        # 29/02 -> 28/02 em ano não bissexto.
        return valor.replace(month=2, day=28, year=valor.year - anos)


def validar_arquivo_imagem_pdf(arquivo):
    if not arquivo:
        return arquivo
    extensao = Path(arquivo.name or '').suffix.lower()
    content_type = (getattr(arquivo, 'content_type', '') or '').lower()
    tipo_ok = content_type.startswith('image/') or content_type == 'application/pdf'
    if extensao not in ARQUIVOS_IMAGEM_PDF_EXTENSOES or (content_type and not tipo_ok):
        raise forms.ValidationError('Envie somente uma imagem ou um arquivo PDF.')
    return arquivo


def apartamentos_para_cadastro():
    """Unidades ativas que podem aparecer no pedido de acesso.

    A validação final diferencia apartamento vago (responsável) de ocupado (filial).
    """
    return Apartamento.objects.filter(
        ativo=True,
        predio__ativo=True,
    ).select_related('predio').distinct().order_by('predio__nome', 'numero')


def credito_competencia(ocupacao, competencia):
    if not ocupacao or not competencia:
        return 0
    return AjusteCompetencia.objects.filter(
        ocupacao=ocupacao,
        competencia=competencia.replace(day=1),
        ativo=True,
    ).aggregate(total=Sum('valor_credito'))['total'] or 0


class DateInput(forms.DateInput):
    input_type = 'date'


class DateTimeInput(forms.DateTimeInput):
    input_type = 'datetime-local'


class MonthInput(forms.DateInput):
    input_type = 'month'


class CadastroUsuarioForm(UserCreationForm):
    nome_completo = forms.CharField(label='Nome completo', max_length=180)
    email = forms.EmailField(label='E-mail')
    cpf = forms.CharField(label='CPF', max_length=14)
    data_nascimento = forms.DateField(label='Data de nascimento', widget=DateInput())
    telefone = forms.CharField(label='Telefone', max_length=30, required=False)
    tipo_vinculo = forms.ChoiceField(
        label='Como você fará parte do apartamento?',
        choices=PerfilUsuario.TIPOS_VINCULO,
        initial='RESPONSAVEL',
        help_text='Responsável solicita uma unidade vaga. Filial entra em uma unidade já ocupada por um responsável.',
    )
    predio = forms.ModelChoiceField(
        label='Prédio', queryset=Predio.objects.none(), empty_label='Selecione o prédio'
    )
    apartamento = forms.ModelChoiceField(
        label='Apartamento',
        queryset=Apartamento.objects.none(),
        empty_label='Selecione primeiro o prédio',
    )
    documento_tipo = forms.ChoiceField(label='Documento de identificação', choices=PerfilUsuario.DOCUMENTOS)
    documento_frente = forms.FileField(
        label='Foto/arquivo da frente do documento',
        widget=forms.ClearableFileInput(attrs={'accept': ARQUIVOS_IMAGEM_PDF_ACCEPT}),
    )
    documento_verso = forms.FileField(
        label='Verso do documento (opcional)', required=False,
        widget=forms.ClearableFileInput(attrs={'accept': ARQUIVOS_IMAGEM_PDF_ACCEPT}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            'nome_completo', 'username', 'email', 'cpf', 'data_nascimento', 'telefone',
            'tipo_vinculo', 'predio', 'apartamento', 'documento_tipo', 'documento_frente', 'documento_verso',
            'password1', 'password2',
        )
        labels = {'username': 'Usuário'}
        help_texts = {'username': 'Use letras, números e @/./+/-/_; sem espaços.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        unidades = apartamentos_para_cadastro()
        self.fields['apartamento'].queryset = unidades
        self.fields['predio'].queryset = Predio.objects.filter(
            ativo=True, apartamentos__in=unidades
        ).distinct().order_by('nome')

        hoje = timezone.localdate()
        self.fields['data_nascimento'].widget.attrs.update({
            'min': subtrair_anos(hoje, 95).isoformat(),
            'max': subtrair_anos(hoje, 16).isoformat(),
        })

    def clean_cpf(self):
        cpf = normalizar_cpf(self.cleaned_data.get('cpf'))
        if len(cpf) != 11:
            raise forms.ValidationError('Informe um CPF com 11 dígitos.')
        if PerfilUsuario.objects.filter(cpf=cpf).exists():
            raise forms.ValidationError('Este CPF já possui uma conta ou solicitação de acesso.')
        return cpf

    def clean_data_nascimento(self):
        nascimento = self.cleaned_data['data_nascimento']
        hoje = timezone.localdate()
        minimo = subtrair_anos(hoje, 95)
        maximo = subtrair_anos(hoje, 16)
        if nascimento > maximo:
            raise forms.ValidationError('É necessário ter pelo menos 16 anos para solicitar acesso.')
        if nascimento < minimo:
            raise forms.ValidationError('A data de nascimento deve corresponder a uma idade de até 95 anos.')
        return nascimento

    def clean_documento_frente(self):
        return validar_arquivo_imagem_pdf(self.cleaned_data.get('documento_frente'))

    def clean_documento_verso(self):
        return validar_arquivo_imagem_pdf(self.cleaned_data.get('documento_verso'))

    def clean(self):
        cleaned = super().clean()
        predio = cleaned.get('predio')
        apartamento = cleaned.get('apartamento')
        tipo = cleaned.get('tipo_vinculo')
        if apartamento and predio and apartamento.predio_id != predio.id:
            self.add_error('apartamento', 'Selecione um apartamento pertencente ao prédio informado.')
        if not apartamento or not tipo:
            return cleaned

        ocupacao = apartamento.ocupacao_atual
        if tipo == 'RESPONSAVEL':
            if ocupacao:
                self.add_error('apartamento', 'Para ser responsável, escolha um apartamento atualmente vago.')
            if PerfilUsuario.objects.filter(
                apartamento_solicitado=apartamento,
                tipo_vinculo_solicitado='RESPONSAVEL',
                status='PENDENTE',
            ).exists():
                self.add_error('apartamento', 'Já existe uma solicitação de responsável pendente para este apartamento.')
        elif tipo == 'FILIAL' and not ocupacao:
            self.add_error('apartamento', 'Para entrar como filial, escolha um apartamento atualmente ocupado.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        nome = self.cleaned_data['nome_completo'].strip()
        partes = nome.split(maxsplit=1)
        user.first_name = partes[0]
        user.last_name = partes[1] if len(partes) > 1 else ''
        user.email = self.cleaned_data['email'].strip()
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
            PerfilUsuario.objects.create(
                user=user,
                papel='MORADOR',
                status='PENDENTE',
                nome_completo=nome,
                cpf=self.cleaned_data['cpf'],
                data_nascimento=self.cleaned_data['data_nascimento'],
                telefone=self.cleaned_data.get('telefone', '').strip(),
                apartamento_solicitado=self.cleaned_data['apartamento'],
                tipo_vinculo_solicitado=self.cleaned_data['tipo_vinculo'],
                documento_tipo=self.cleaned_data['documento_tipo'],
                documento_frente=self.cleaned_data['documento_frente'],
                documento_verso=self.cleaned_data.get('documento_verso'),
            )
        return user


class RedefinirSenhaLogadoForm(SetPasswordForm):
    """Permite a um usuário já autenticado definir uma nova senha sem repetir a antiga."""

    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields['new_password1'].label = 'Nova senha'
        self.fields['new_password2'].label = 'Confirmar nova senha'


class PerfilAcessoForm(forms.ModelForm):
    remover_residencia_ao_promover = forms.BooleanField(
        label='Ao promover para Administrador, encerrar a ocupação atual e liberar o apartamento',
        required=False, initial=True,
        help_text='Se marcado, a ocupação atual (incluindo filiais) será encerrada e a unidade ficará vaga. O histórico será preservado.',
    )

    class Meta:
        model = PerfilUsuario
        fields = ['papel', 'status']
        labels = {'papel': 'Perfil de acesso', 'status': 'Situação da conta'}


class PermissoesAdministradorForm(forms.ModelForm):
    predios_administrados = forms.ModelMultipleChoiceField(
        label='Prédios permitidos', queryset=Predio.objects.filter(ativo=True).order_by('nome'),
        required=False, widget=forms.CheckboxSelectMultiple,
        help_text='Se "Acesso a todos os prédios" estiver marcado, esta seleção é ignorada.',
    )

    class Meta:
        model = PerfilUsuario
        fields = ['admin_acesso_todos_predios', 'predios_administrados']
        labels = {'admin_acesso_todos_predios': 'Acesso a todos os prédios'}

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('admin_acesso_todos_predios') and not cleaned.get('predios_administrados'):
            self.add_error('predios_administrados', 'Selecione ao menos um prédio ou libere acesso a todos.')
        return cleaned


class AprovarMoradorForm(forms.Form):
    data_inicio = forms.DateField(
        label='Data de início da ocupação', widget=DateInput(),
        help_text='Pode começar hoje ou em no máximo 1 mês.',
    )
    dia_vencimento = forms.IntegerField(label='Dia do vencimento', min_value=1, max_value=31, initial=10)
    valor_aluguel = forms.DecimalField(label='Valor do aluguel', max_digits=10, decimal_places=2, min_value=0)
    valor_mobilia = forms.DecimalField(label='Adicional de mobília', max_digits=10, decimal_places=2, min_value=0, initial=0)
    observacoes = forms.CharField(label='Observações da ocupação', widget=forms.Textarea, required=False)

    def __init__(self, *args, perfil=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.perfil = perfil
        apartamento = perfil.apartamento_solicitado if perfil else None
        hoje = timezone.localdate()
        self.fields['data_inicio'].widget.attrs.update({
            'min': hoje.isoformat(),
            'max': adicionar_meses(hoje, 1).isoformat(),
        })
        if apartamento and not self.is_bound:
            self.fields['data_inicio'].initial = hoje
            self.fields['valor_aluguel'].initial = apartamento.valor_aluguel_base
            self.fields['valor_mobilia'].initial = apartamento.valor_mobilia if apartamento.mobiliado else 0

    def clean_data_inicio(self):
        valor = self.cleaned_data['data_inicio']
        hoje = timezone.localdate()
        if valor < hoje:
            raise forms.ValidationError('A nova ocupação não pode começar em uma data passada neste fluxo.')
        if valor > adicionar_meses(hoje, 1):
            raise forms.ValidationError('A ocupação pode ser agendada para no máximo 1 mês à frente.')
        return valor


class AprovarFilialForm(forms.Form):
    data_inicio = forms.DateField(
        label='Data de entrada como filial', widget=DateInput(),
        help_text='Pode começar hoje ou em no máximo 1 mês.',
    )
    observacoes = forms.CharField(label='Observações do vínculo', widget=forms.Textarea, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoje = timezone.localdate()
        self.fields['data_inicio'].initial = hoje
        self.fields['data_inicio'].widget.attrs.update({
            'min': hoje.isoformat(),
            'max': adicionar_meses(hoje, 1).isoformat(),
        })

    def clean_data_inicio(self):
        valor = self.cleaned_data['data_inicio']
        hoje = timezone.localdate()
        if valor < hoje:
            raise forms.ValidationError('A entrada como filial não pode começar em uma data passada neste fluxo.')
        if valor > adicionar_meses(hoje, 1):
            raise forms.ValidationError('O vínculo pode ser agendado para no máximo 1 mês à frente.')
        return valor


class TrocarResponsavelForm(forms.Form):
    novo_responsavel = forms.ModelChoiceField(label='Novo responsável', queryset=Morador.objects.none())
    data_alteracao = forms.DateField(label='Data da alteração', widget=DateInput())
    manter_anterior_como_filial = forms.BooleanField(
        label='Manter o responsável anterior como morador filial', required=False,
        help_text='Marque se ele continuará morando no apartamento. Se estiver saindo, deixe desmarcado.',
    )
    observacoes = forms.CharField(label='Observações', widget=forms.Textarea, required=False)

    def __init__(self, *args, ocupacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ocupacao = ocupacao
        hoje = timezone.localdate()
        if ocupacao:
            self.fields['novo_responsavel'].queryset = Morador.objects.filter(
                vinculos_ocupacao__ocupacao=ocupacao,
                vinculos_ocupacao__ativa=True,
                vinculos_ocupacao__data_fim__isnull=True,
            ).distinct().order_by('nome_completo')
            self.fields['data_alteracao'].widget.attrs.update({
                'min': ocupacao.data_inicio.isoformat(), 'max': hoje.isoformat()
            })
        self.fields['data_alteracao'].initial = hoje

    def clean_data_alteracao(self):
        valor = self.cleaned_data['data_alteracao']
        hoje = timezone.localdate()
        if valor > hoje:
            raise forms.ValidationError('A troca de responsável não pode ser registrada em data futura.')
        if self.ocupacao and valor < self.ocupacao.data_inicio:
            raise forms.ValidationError('A data não pode ser anterior ao início da ocupação.')
        return valor


class OcupacaoChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        status = 'atual' if obj.ativa and obj.data_fim is None else 'encerrada'
        return f'{obj.morador.nome_completo} - {obj.apartamento.predio.nome} - Apt. {obj.apartamento.numero} ({status})'


class PredioForm(forms.ModelForm):
    quantidade_apartamentos = forms.IntegerField(
        label='Quantidade de apartamentos', min_value=0, max_value=500, initial=0, required=False,
        help_text='Ao salvar, o sistema cria automaticamente as unidades 1, 2, 3... Você poderá editar número, valor e observações depois.',
    )

    class Meta:
        model = Predio
        fields = ['nome', 'endereco', 'quantidade_apartamentos', 'observacoes', 'ativo']


class PredioEditForm(forms.ModelForm):
    class Meta:
        model = Predio
        fields = ['nome', 'endereco', 'observacoes', 'ativo']


class ApartamentoForm(forms.ModelForm):
    class Meta:
        model = Apartamento
        fields = ['predio', 'numero', 'andar', 'valor_aluguel_base', 'mobiliado', 'valor_mobilia', 'observacoes', 'ativo']
        labels = {'valor_aluguel_base': 'Valor base do aluguel', 'valor_mobilia': 'Valor adicional da mobília'}

    def __init__(self, *args, predios_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if predios_queryset is not None:
            self.fields['predio'].queryset = predios_queryset


class MoradorForm(forms.ModelForm):
    class Meta:
        model = Morador
        fields = ['nome_completo', 'cpf', 'rg', 'telefone', 'email', 'data_nascimento', 'observacoes', 'ativo']
        widgets = {'data_nascimento': DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoje = timezone.localdate()
        self.fields['data_nascimento'].widget.attrs.update({
            'min': subtrair_anos(hoje, 95).isoformat(),
            'max': subtrair_anos(hoje, 16).isoformat(),
        })

    def clean_data_nascimento(self):
        nascimento = self.cleaned_data.get('data_nascimento')
        if not nascimento:
            return nascimento
        hoje = timezone.localdate()
        if nascimento > subtrair_anos(hoje, 16):
            raise forms.ValidationError('O morador precisa ter pelo menos 16 anos.')
        if nascimento < subtrair_anos(hoje, 95):
            raise forms.ValidationError('A data de nascimento deve corresponder a uma idade de até 95 anos.')
        return nascimento


class DocumentoMoradorForm(forms.ModelForm):
    arquivo = forms.FileField(
        label='Arquivo',
        widget=forms.ClearableFileInput(attrs={'accept': ARQUIVOS_IMAGEM_PDF_ACCEPT}),
    )

    class Meta:
        model = DocumentoMorador
        fields = ['tipo', 'arquivo', 'descricao']

    def clean_arquivo(self):
        return validar_arquivo_imagem_pdf(self.cleaned_data.get('arquivo'))


class OcupacaoForm(forms.ModelForm):
    class Meta:
        model = Ocupacao
        fields = ['morador', 'apartamento', 'data_inicio', 'data_fim', 'dia_vencimento', 'valor_aluguel', 'valor_mobilia', 'ativa', 'observacoes']
        widgets = {'data_inicio': DateInput(), 'data_fim': DateInput()}
        labels = {
            'data_fim': 'Data fim (opcional)', 'dia_vencimento': 'Dia do vencimento',
            'valor_aluguel': 'Valor do aluguel', 'valor_mobilia': 'Valor adicional da mobília',
        }
        help_texts = {'data_fim': 'Deixe em branco enquanto o morador continuar no apartamento.'}

    def __init__(self, *args, predios_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_fim'].required = False
        hoje = timezone.localdate()
        self.fields['data_inicio'].widget.attrs.update({'max': adicionar_meses(hoje, 1).isoformat()})
        if predios_queryset is not None:
            self.fields['apartamento'].queryset = Apartamento.objects.filter(
                predio__in=predios_queryset, ativo=True
            ).select_related('predio').distinct()

    def clean_data_inicio(self):
        data_inicio = self.cleaned_data['data_inicio']
        hoje = timezone.localdate()
        if data_inicio > adicionar_meses(hoje, 1):
            raise forms.ValidationError('A ocupação pode começar em no máximo 1 mês à frente.')
        return data_inicio


class TransferenciaMoradorForm(forms.Form):
    novo_apartamento = forms.ModelChoiceField(label='Novo apartamento', queryset=Apartamento.objects.none())
    data_mudanca = forms.DateField(
        label='Data da mudança', widget=DateInput(),
        help_text='A mudança pode ser registrada para no máximo 1 mês à frente.',
    )
    dia_vencimento = forms.IntegerField(label='Dia do vencimento', min_value=1, max_value=31, initial=10)
    valor_aluguel = forms.DecimalField(label='Valor do aluguel', max_digits=10, decimal_places=2)
    valor_mobilia = forms.DecimalField(label='Adicional de mobília', max_digits=10, decimal_places=2, initial=0)
    observacoes = forms.CharField(label='Observações', widget=forms.Textarea, required=False)

    def __init__(self, *args, morador=None, predios_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.morador = morador
        qs = Apartamento.objects.filter(ativo=True).exclude(
            ocupacoes__ativa=True, ocupacoes__data_fim__isnull=True
        ).select_related('predio').distinct().order_by('predio__nome', 'numero')
        if predios_queryset is not None:
            qs = qs.filter(predio__in=predios_queryset)
        self.fields['novo_apartamento'].queryset = qs
        hoje = timezone.localdate()
        self.fields['data_mudanca'].widget.attrs.update({'max': adicionar_meses(hoje, 1).isoformat()})
        atual = morador.ocupacao_atual if morador else None
        if atual and not self.is_bound:
            self.fields['dia_vencimento'].initial = atual.dia_vencimento
            self.fields['valor_aluguel'].initial = atual.valor_aluguel
            self.fields['valor_mobilia'].initial = atual.valor_mobilia

    def clean_data_mudanca(self):
        data_mudanca = self.cleaned_data['data_mudanca']
        atual = self.morador.ocupacao_atual if self.morador else None
        if atual and data_mudanca <= atual.data_inicio:
            raise forms.ValidationError('A mudança precisa ocorrer depois do início da ocupação atual.')
        if data_mudanca > adicionar_meses(timezone.localdate(), 1):
            raise forms.ValidationError('A mudança pode ser agendada para no máximo 1 mês à frente.')
        return data_mudanca


class PagamentoForm(forms.Form):
    ocupacao = OcupacaoChoiceField(queryset=Ocupacao.objects.none(), label='Ocupação / quem pagou')
    competencia = forms.DateField(
        label='Competência', input_formats=['%Y-%m'], widget=MonthInput(format='%Y-%m'),
        help_text='Permitido do mês atual até no máximo 6 meses à frente.',
    )
    valor_pago = forms.DecimalField(label='Valor deste pagamento', max_digits=10, decimal_places=2, min_value=0.01)
    data_pagamento = forms.DateField(
        label='Data do pagamento', widget=DateInput(),
        help_text='Não pode ser futura nem anterior a 6 meses.',
    )
    forma_pagamento = forms.ChoiceField(
        label='Forma de pagamento', choices=Pagamento.FORMAS, required=False,
    )
    justificativa_excedente = forms.CharField(
        label='Motivo do valor acima do saldo da competência', widget=forms.Textarea, required=False,
        help_text='Obrigatório quando este lançamento ultrapassar o saldo ainda devido da competência.',
    )
    descricao_excedente_recibo = forms.CharField(
        label='Como o excedente deve aparecer no recibo', widget=forms.Textarea, required=False,
        help_text='Você pode corrigir a descrição antes de gerar o recibo.',
    )
    observacoes = forms.CharField(label='Observações internas', widget=forms.Textarea, required=False)
    gerar_credito_proxima_competencia = forms.BooleanField(
        label='Usar o excedente deste pagamento como crédito no próximo mês', required=False,
        help_text='Se a competência já estiver quitada, qualquer novo valor só pode ser registrado como crédito para o próximo mês.',
    )

    def __init__(self, *args, predios_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Ocupacao.objects.select_related('morador', 'apartamento__predio').order_by('-ativa', 'morador__nome_completo')
        if predios_queryset is not None:
            qs = qs.filter(apartamento__predio__in=predios_queryset)
        self.fields['ocupacao'].queryset = qs
        hoje = timezone.localdate()
        mes_atual = hoje.replace(day=1)
        self.fields['competencia'].widget.attrs.update({
            'min': mes_atual.strftime('%Y-%m'), 'max': adicionar_meses(mes_atual, 6).strftime('%Y-%m')
        })
        self.fields['data_pagamento'].widget.attrs.update({
            'min': adicionar_meses(hoje, -6).isoformat(), 'max': hoje.isoformat()
        })

    def clean_competencia(self):
        competencia = self.cleaned_data['competencia'].replace(day=1)
        atual = timezone.localdate().replace(day=1)
        if competencia < atual or competencia > adicionar_meses(atual, 6):
            raise forms.ValidationError('A competência deve ficar entre o mês atual e no máximo 6 meses à frente.')
        return competencia

    def clean_data_pagamento(self):
        data_pagamento = self.cleaned_data['data_pagamento']
        hoje = timezone.localdate()
        if data_pagamento > hoje:
            raise forms.ValidationError('O pagamento não pode ser registrado em uma data futura.')
        if data_pagamento < adicionar_meses(hoje, -6):
            raise forms.ValidationError('A data do pagamento não pode ser anterior a aproximadamente 6 meses.')
        return data_pagamento

    def clean(self):
        cleaned = super().clean()
        ocupacao = cleaned.get('ocupacao')
        competencia = cleaned.get('competencia')
        valor = cleaned.get('valor_pago')
        if not ocupacao or not competencia or valor is None:
            return cleaned
        competencia = competencia.replace(day=1)
        mensal = ocupacao.valor_total_mensal
        pagamento_existente = Pagamento.objects.filter(ocupacao=ocupacao, competencia=competencia).first()
        pago_atual = pagamento_existente.valor_pago if pagamento_existente else Decimal('0')
        if pago_atual + valor > mensal * Decimal('2'):
            self.add_error(
                'valor_pago',
                f'A soma dos pagamentos desta competência não pode superar o dobro do aluguel mensal (R$ {mensal * 2:.2f}).'
            )
            return cleaned
        credito = AjusteCompetencia.objects.filter(
            ocupacao=ocupacao, competencia=competencia, ativo=True
        ).aggregate(total=Sum('valor_credito'))['total'] or Decimal('0')
        devido_ajustado = max(mensal - credito, Decimal('0'))
        saldo_antes = max(devido_ajustado - pago_atual, Decimal('0'))
        excedente_lancamento = max(valor - saldo_antes, Decimal('0'))
        gerar_credito = cleaned.get('gerar_credito_proxima_competencia', False)
        if excedente_lancamento > 0 and not (cleaned.get('justificativa_excedente') or '').strip():
            self.add_error('justificativa_excedente', 'Explique o motivo do valor acima do saldo ainda devido.')
        if pago_atual >= devido_ajustado and valor > 0 and not gerar_credito:
            self.add_error(
                'gerar_credito_proxima_competencia',
                'Esta competência já está quitada. Um pagamento adicional só pode ser registrado como crédito para o próximo mês.'
            )
        if gerar_credito and excedente_lancamento <= 0:
            self.add_error('gerar_credito_proxima_competencia', 'Este lançamento não possui excedente para transformar em crédito.')
        if gerar_credito and pagamento_existente:
            credito_ja_destinado = pagamento_existente.lancamentos.filter(
                gerar_credito_proxima_competencia=True
            ).aggregate(total=Sum('valor_excedente'))['total'] or Decimal('0')
            if credito_ja_destinado + excedente_lancamento > mensal:
                self.add_error(
                    'valor_pago',
                    f'O crédito gerado para o próximo mês não pode superar uma mensalidade (R$ {mensal:.2f}).'
                )
        elif gerar_credito and excedente_lancamento > mensal:
            self.add_error(
                'valor_pago',
                f'O crédito gerado para o próximo mês não pode superar uma mensalidade (R$ {mensal:.2f}).'
            )
        if excedente_lancamento > 0 and not (cleaned.get('descricao_excedente_recibo') or '').strip():
            cleaned['descricao_excedente_recibo'] = (cleaned.get('justificativa_excedente') or '').strip()
        cleaned['_pagamento_existente'] = pagamento_existente
        cleaned['_pago_atual'] = pago_atual
        cleaned['_credito_competencia'] = credito
        cleaned['_devido_ajustado'] = devido_ajustado
        cleaned['_excedente_lancamento'] = excedente_lancamento
        return cleaned


class ComprovantePagamentoForm(forms.ModelForm):
    competencia = forms.DateField(
        label='Competência', input_formats=['%Y-%m'], widget=MonthInput(format='%Y-%m'),
        help_text='Permitido do mês atual até no máximo 6 meses à frente.',
    )
    data_pagamento = forms.DateField(
        label='Data do pagamento', widget=DateInput(),
        help_text='Não pode ser futura nem anterior a 6 meses.',
    )
    arquivo = forms.FileField(
        label='Comprovante (opcional)', required=False,
        widget=forms.ClearableFileInput(attrs={'accept': ARQUIVOS_IMAGEM_PDF_ACCEPT}),
        help_text='Opcional. Envie somente imagem ou PDF. Pagamentos em dinheiro podem ser informados sem arquivo.',
    )

    class Meta:
        model = ComprovantePagamento
        fields = [
            'competencia', 'valor_informado', 'data_pagamento', 'forma_pagamento',
            'arquivo', 'justificativa_excedente', 'observacoes',
        ]
        labels = {
            'valor_informado': 'Valor pago',
            'justificativa_excedente': 'Motivo do valor acima do devido',
            'observacoes': 'Observações',
        }
        help_texts = {
            'justificativa_excedente': 'Obrigatório quando você informar um valor maior que o devido nesta competência.',
        }

    def __init__(self, *args, ocupacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ocupacao = ocupacao
        hoje = timezone.localdate()
        mes_atual = hoje.replace(day=1)
        self.fields['competencia'].widget.attrs.update({
            'min': mes_atual.strftime('%Y-%m'),
            'max': adicionar_meses(mes_atual, 6).strftime('%Y-%m'),
        })
        self.fields['data_pagamento'].widget.attrs.update({
            'min': adicionar_meses(hoje, -6).isoformat(),
            'max': hoje.isoformat(),
        })

    def clean_competencia(self):
        competencia = self.cleaned_data['competencia'].replace(day=1)
        atual = timezone.localdate().replace(day=1)
        if competencia < atual or competencia > adicionar_meses(atual, 6):
            raise forms.ValidationError('A competência deve ficar entre o mês atual e no máximo 6 meses à frente.')
        return competencia

    def clean_data_pagamento(self):
        data_pagamento = self.cleaned_data['data_pagamento']
        hoje = timezone.localdate()
        if data_pagamento > hoje:
            raise forms.ValidationError('A data do pagamento não pode estar no futuro.')
        if data_pagamento < adicionar_meses(hoje, -6):
            raise forms.ValidationError('A data do pagamento não pode ser anterior a aproximadamente 6 meses.')
        return data_pagamento

    def clean_arquivo(self):
        return validar_arquivo_imagem_pdf(self.cleaned_data.get('arquivo'))

    def clean(self):
        cleaned = super().clean()
        if not self.ocupacao:
            return cleaned
        competencia = cleaned.get('competencia')
        valor = cleaned.get('valor_informado')
        if not competencia or valor is None:
            return cleaned
        competencia = competencia.replace(day=1)
        mensal = self.ocupacao.valor_total_mensal
        pagamento_existente = Pagamento.objects.filter(ocupacao=self.ocupacao, competencia=competencia).first()
        pago_atual = pagamento_existente.valor_pago if pagamento_existente else Decimal('0')
        if pago_atual + valor > mensal * Decimal('2'):
            self.add_error(
                'valor_informado',
                f'A soma dos pagamentos desta competência não pode superar o dobro do aluguel mensal (R$ {mensal * 2:.2f}).'
            )
            return cleaned
        credito = AjusteCompetencia.objects.filter(
            ocupacao=self.ocupacao, competencia=competencia, ativo=True
        ).aggregate(total=Sum('valor_credito'))['total'] or Decimal('0')
        devido_ajustado = max(mensal - credito, Decimal('0'))
        saldo_antes = max(devido_ajustado - pago_atual, Decimal('0'))
        excedente_lancamento = max(valor - saldo_antes, Decimal('0'))
        if excedente_lancamento > 0 and not (cleaned.get('justificativa_excedente') or '').strip():
            self.add_error('justificativa_excedente', 'Explique o motivo do valor acima do saldo ainda devido.')
        cleaned['_pagamento_existente'] = pagamento_existente
        cleaned['_pago_atual'] = pago_atual
        cleaned['_devido_ajustado'] = devido_ajustado
        cleaned['_excedente_lancamento'] = excedente_lancamento
        return cleaned


class AprovarComprovanteForm(forms.Form):
    descricao_excedente_recibo = forms.CharField(
        label='Descrição do excedente no recibo', widget=forms.Textarea, required=False,
        help_text='Edite este texto se a justificativa enviada pelo morador estiver incompleta ou incorreta.',
    )
    gerar_credito_proxima_competencia = forms.BooleanField(
        label='Transformar o excedente em crédito para o próximo mês', required=False,
        help_text='O próximo mês terá o valor devido reduzido por este crédito.',
    )

    def __init__(self, *args, comprovante=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.comprovante = comprovante
        if comprovante and not self.is_bound:
            self.fields['descricao_excedente_recibo'].initial = comprovante.justificativa_excedente

    def clean(self):
        cleaned = super().clean()
        c = self.comprovante
        if not c:
            return cleaned
        competencia = c.competencia.replace(day=1)
        credito = AjusteCompetencia.objects.filter(
            ocupacao=c.ocupacao, competencia=competencia, ativo=True
        ).aggregate(total=Sum('valor_credito'))['total'] or Decimal('0')
        devido = max(c.ocupacao.valor_total_mensal - credito, Decimal('0'))
        pagamento_existente = Pagamento.objects.filter(ocupacao=c.ocupacao, competencia=competencia).first()
        pago_atual = pagamento_existente.valor_pago if pagamento_existente else Decimal('0')
        saldo_antes = max(devido - pago_atual, Decimal('0'))
        excedente = max(c.valor_informado - saldo_antes, Decimal('0'))
        if pago_atual + c.valor_informado > c.ocupacao.valor_total_mensal * Decimal('2'):
            raise forms.ValidationError('A soma dos pagamentos desta competência ultrapassa o limite de duas mensalidades.')
        if excedente > 0 and not (cleaned.get('descricao_excedente_recibo') or '').strip():
            self.add_error('descricao_excedente_recibo', 'Informe como o valor excedente deve aparecer no recibo.')
        if pago_atual >= devido and c.valor_informado > 0 and not cleaned.get('gerar_credito_proxima_competencia'):
            self.add_error(
                'gerar_credito_proxima_competencia',
                'A competência já estava quitada. Este pagamento adicional só pode ser aprovado como crédito para o próximo mês.'
            )
        if cleaned.get('gerar_credito_proxima_competencia') and excedente <= 0:
            self.add_error('gerar_credito_proxima_competencia', 'Este pagamento não possui excedente.')
        if cleaned.get('gerar_credito_proxima_competencia'):
            credito_ja_destinado = Decimal('0')
            if pagamento_existente:
                credito_ja_destinado = pagamento_existente.lancamentos.filter(
                    gerar_credito_proxima_competencia=True
                ).aggregate(total=Sum('valor_excedente'))['total'] or Decimal('0')
            mensal = c.ocupacao.valor_total_mensal
            if credito_ja_destinado + excedente > mensal:
                self.add_error(
                    'gerar_credito_proxima_competencia',
                    f'O crédito para o próximo mês não pode superar uma mensalidade (R$ {mensal:.2f}).'
                )
        cleaned['_credito_competencia'] = credito
        cleaned['_devido_ajustado'] = devido
        cleaned['_pago_atual'] = pago_atual
        cleaned['_excedente_lancamento'] = excedente
        return cleaned


class PagamentoExcedenteForm(forms.Form):
    descricao_excedente_recibo = forms.CharField(
        label='Descrição do excedente no recibo', widget=forms.Textarea, required=True,
    )
    gerar_credito_proxima_competencia = forms.BooleanField(
        label='Usar o excedente como crédito no próximo mês', required=False,
    )

    def __init__(self, *args, pagamento=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pagamento = pagamento
        if pagamento and not self.is_bound:
            self.fields['descricao_excedente_recibo'].initial = pagamento.descricao_excedente_recibo or pagamento.justificativa_excedente
            self.fields['gerar_credito_proxima_competencia'].initial = hasattr(pagamento, 'credito_gerado') and pagamento.credito_gerado.ativo

    def clean(self):
        cleaned = super().clean()
        if self.pagamento and self.pagamento.valor_excedente <= 0:
            raise forms.ValidationError('Este pagamento não possui valor excedente.')
        if self.pagamento and cleaned.get('gerar_credito_proxima_competencia'):
            mensal = self.pagamento.valor_mensal_referencia
            if self.pagamento.valor_excedente > mensal:
                self.add_error(
                    'gerar_credito_proxima_competencia',
                    f'O crédito para o próximo mês não pode superar uma mensalidade (R$ {mensal:.2f}).'
                )
        return cleaned


class ComprovanteAdminArquivoForm(forms.Form):
    arquivo = forms.FileField(
        label='Anexar/alterar comprovante',
        widget=forms.ClearableFileInput(attrs={'accept': ARQUIVOS_IMAGEM_PDF_ACCEPT}),
    )

    def clean_arquivo(self):
        return validar_arquivo_imagem_pdf(self.cleaned_data.get('arquivo'))


class ContaImovelForm(forms.ModelForm):
    class Meta:
        model = ContaImovel
        fields = ['predio', 'apartamento', 'tipo', 'fornecedor', 'rotulo_codigo', 'codigo', 'url_portal', 'observacoes', 'ativa']

    def __init__(self, *args, predios_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if predios_queryset is not None:
            self.fields['predio'].queryset = predios_queryset
            self.fields['apartamento'].queryset = Apartamento.objects.filter(predio__in=predios_queryset).select_related('predio')

    def clean(self):
        cleaned = super().clean()
        predio = cleaned.get('predio')
        apartamento = cleaned.get('apartamento')
        if apartamento and predio and apartamento.predio_id != predio.id:
            self.add_error('apartamento', 'O apartamento precisa pertencer ao prédio selecionado.')
        return cleaned


class PagamentoContaImovelForm(forms.ModelForm):
    competencia = forms.DateField(
        label='Competência da conta', input_formats=['%Y-%m'], widget=MonthInput(format='%Y-%m'),
        help_text='Mês ao qual esta despesa pertence.'
    )
    data_pagamento = forms.DateField(label='Data do pagamento', widget=DateInput())
    comprovante = forms.FileField(
        label='Comprovante (opcional)', required=False,
        widget=forms.ClearableFileInput(attrs={'accept': ARQUIVOS_IMAGEM_PDF_ACCEPT}),
        help_text='Aceita foto ou PDF.'
    )

    class Meta:
        model = PagamentoContaImovel
        fields = ['competencia', 'valor_pago', 'data_pagamento', 'comprovante', 'observacoes']
        labels = {'valor_pago': 'Valor pago', 'observacoes': 'Observações'}

    def clean_comprovante(self):
        return validar_arquivo_imagem_pdf(self.cleaned_data.get('comprovante'))

    def clean(self):
        cleaned = super().clean()
        competencia = cleaned.get('competencia')
        data_pagamento = cleaned.get('data_pagamento')
        valor_pago = cleaned.get('valor_pago')
        hoje = timezone.localdate()
        primeiro_atual = hoje.replace(day=1)
        if competencia:
            competencia = competencia.replace(day=1)
            cleaned['competencia'] = competencia
            if competencia > primeiro_atual:
                self.add_error('competencia', 'Não é possível registrar uma conta de competência futura.')
        if data_pagamento and data_pagamento > hoje:
            self.add_error('data_pagamento', 'A data do pagamento não pode estar no futuro.')
        if valor_pago is not None and valor_pago <= 0:
            self.add_error('valor_pago', 'Informe um valor pago maior que zero.')
        return cleaned


class RemoverHistoricoMoradorForm(forms.Form):
    confirmacao = forms.CharField(
        label='Digite REMOVER para confirmar', max_length=20,
        help_text='A ação remove dados pessoais e documentos do ex-morador. Valores financeiros históricos permanecem anonimizados.'
    )

    def clean_confirmacao(self):
        valor = (self.cleaned_data.get('confirmacao') or '').strip().upper()
        if valor != 'REMOVER':
            raise forms.ValidationError('Digite REMOVER exatamente para confirmar.')
        return valor


class RelatorioFinanceiroForm(forms.Form):
    TIPOS_PDF = [
        ('RELATORIO', 'Relatório financeiro / resultado líquido'),
        ('COMPROVANTE', 'Comprovante consolidado de pagamentos de um apartamento'),
    ]
    ESCOPOS = [
        ('TODOS', 'Todos os prédios'),
        ('PREDIOS', 'Prédios específicos'),
        ('APARTAMENTOS', 'Apartamentos específicos'),
    ]

    tipo_pdf = forms.ChoiceField(label='Tipo de PDF', choices=TIPOS_PDF, initial='RELATORIO')
    competencia_inicio = forms.DateField(
        label='Mês inicial', input_formats=['%Y-%m'], widget=MonthInput(format='%Y-%m')
    )
    competencia_fim = forms.DateField(
        label='Mês final', input_formats=['%Y-%m'], widget=MonthInput(format='%Y-%m')
    )
    escopo = forms.ChoiceField(label='Abrangência', choices=ESCOPOS, initial='TODOS')
    predios = forms.ModelMultipleChoiceField(
        label='Prédios', queryset=Predio.objects.none(), required=False, widget=forms.CheckboxSelectMultiple
    )
    apartamentos = forms.ModelMultipleChoiceField(
        label='Apartamentos', queryset=Apartamento.objects.none(), required=False,
        widget=forms.SelectMultiple(attrs={'size': 10})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['predios'].queryset = Predio.objects.all().order_by('nome')
        self.fields['apartamentos'].queryset = Apartamento.objects.select_related('predio').all().order_by('predio__nome', 'numero')
        hoje = timezone.localdate()
        primeiro_atual = hoje.replace(day=1)
        anterior = adicionar_meses(primeiro_atual, -1)
        if not self.is_bound:
            self.fields['competencia_inicio'].initial = anterior
            self.fields['competencia_fim'].initial = anterior

    def clean(self):
        cleaned = super().clean()
        inicio = cleaned.get('competencia_inicio')
        fim = cleaned.get('competencia_fim')
        escopo = cleaned.get('escopo')
        tipo_pdf = cleaned.get('tipo_pdf')
        predios = cleaned.get('predios')
        apartamentos = cleaned.get('apartamentos')
        primeiro_atual = timezone.localdate().replace(day=1)

        if inicio:
            inicio = inicio.replace(day=1)
            cleaned['competencia_inicio'] = inicio
        if fim:
            fim = fim.replace(day=1)
            cleaned['competencia_fim'] = fim
        if inicio and fim and inicio > fim:
            self.add_error('competencia_fim', 'O mês final não pode ser anterior ao mês inicial.')
        if inicio and inicio >= primeiro_atual:
            self.add_error('competencia_inicio', 'O período deve começar em um mês já encerrado.')
        if fim and fim >= primeiro_atual:
            self.add_error('competencia_fim', 'Não é permitido gerar resultado do mês atual ou de meses futuros.')
        if escopo == 'PREDIOS' and not predios:
            self.add_error('predios', 'Selecione pelo menos um prédio.')
        if escopo == 'APARTAMENTOS' and not apartamentos:
            self.add_error('apartamentos', 'Selecione pelo menos um apartamento.')
        if tipo_pdf == 'COMPROVANTE':
            if escopo != 'APARTAMENTOS':
                self.add_error('escopo', 'O comprovante consolidado exige “Apartamentos específicos”.')
            elif apartamentos is not None and len(apartamentos) != 1:
                self.add_error('apartamentos', 'Selecione exatamente um apartamento.')
        return cleaned


class ComunicadoForm(forms.ModelForm):
    class Meta:
        model = Comunicado
        fields = ['tipo', 'alcance', 'predio', 'morador', 'titulo', 'mensagem']
        labels = {'alcance': 'Enviar para', 'predio': 'Prédio', 'morador': 'Morador específico'}

    def __init__(self, *args, predios_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.predios_queryset = predios_queryset if predios_queryset is not None else Predio.objects.all()
        self.fields['predio'].required = False
        self.fields['morador'].required = False
        self.fields['predio'].queryset = self.predios_queryset
        moradores = Morador.objects.filter(
            perfil_usuario__status='ATIVO',
        ).filter(
            Q(ocupacoes__ativa=True, ocupacoes__data_fim__isnull=True)
            | Q(vinculos_ocupacao__ativa=True, vinculos_ocupacao__data_fim__isnull=True)
        ).distinct()
        if predios_queryset is not None:
            moradores = moradores.filter(
                Q(ocupacoes__apartamento__predio__in=predios_queryset, ocupacoes__ativa=True, ocupacoes__data_fim__isnull=True)
                | Q(vinculos_ocupacao__ocupacao__apartamento__predio__in=predios_queryset,
                    vinculos_ocupacao__ativa=True, vinculos_ocupacao__data_fim__isnull=True)
            ).distinct()
        self.fields['morador'].queryset = moradores.order_by('nome_completo')

    def clean(self):
        cleaned = super().clean()
        alcance = cleaned.get('alcance')
        predio = cleaned.get('predio')
        morador = cleaned.get('morador')

        if alcance == 'TODOS':
            cleaned['predio'] = None
            cleaned['morador'] = None
        elif alcance == 'PREDIO':
            cleaned['morador'] = None
            if not predio:
                self.add_error('predio', 'Selecione o prédio que receberá o comunicado.')
        elif alcance == 'MORADOR':