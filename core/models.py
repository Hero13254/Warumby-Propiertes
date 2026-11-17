from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class Predio(models.Model):
    nome = models.CharField(max_length=120)
    endereco = models.CharField(max_length=255, blank=True)
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Prédio'
        verbose_name_plural = 'Prédios'

    def __str__(self):
        return self.nome


class Apartamento(models.Model):
    predio = models.ForeignKey(Predio, on_delete=models.CASCADE, related_name='apartamentos')
    numero = models.CharField(max_length=20)
    andar = models.CharField(max_length=20, blank=True)
    valor_aluguel_base = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    mobiliado = models.BooleanField(default=False)
    valor_mobilia = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['predio__nome', 'numero']
        constraints = [
            models.UniqueConstraint(fields=['predio', 'numero'], name='apartamento_unico_por_predio')
        ]
        verbose_name = 'Apartamento'
        verbose_name_plural = 'Apartamentos'

    def __str__(self):
        return f'{self.predio.nome} - Apt. {self.numero}'

    @property
    def valor_total_padrao(self):
        return self.valor_aluguel_base + (self.valor_mobilia if self.mobiliado else Decimal('0'))

    @property
    def ocupacao_atual(self):
        return self.ocupacoes.filter(ativa=True, data_fim__isnull=True).select_related('morador').first()


class Morador(models.Model):
    nome_completo = models.CharField(max_length=180)
    cpf = models.CharField(max_length=14, blank=True, db_index=True)
    rg = models.CharField(max_length=30, blank=True)
    telefone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    anonimizado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['nome_completo']
        verbose_name = 'Morador'
        verbose_name_plural = 'Moradores'

    def __str__(self):
        return self.nome_completo

    @property
    def ocupacao_atual(self):
        principal = self.ocupacoes.filter(ativa=True, data_fim__isnull=True).select_related('apartamento__predio').first()
        if principal:
            return principal
        vinculo = self.vinculos_ocupacao.filter(ativa=True, data_fim__isnull=True).select_related(
            'ocupacao__apartamento__predio', 'ocupacao__morador'
        ).first()
        return vinculo.ocupacao if vinculo else None

    @property
    def eh_responsavel_atual(self):
        ocupacao = self.ocupacao_atual
        return bool(ocupacao and ocupacao.morador_id == self.id)


class DocumentoMorador(models.Model):
    TIPOS = [
        ('RG', 'RG'), ('CPF', 'CPF'), ('CNH', 'CNH'),
        ('CONTRATO', 'Contrato'), ('COMPROVANTE', 'Comprovante'), ('OUTRO', 'Outro'),
    ]
    morador = models.ForeignKey(Morador, on_delete=models.CASCADE, related_name='documentos')
    tipo = models.CharField(max_length=20, choices=TIPOS, default='OUTRO')
    arquivo = models.FileField(upload_to='documentos/%Y/%m/')
    descricao = models.CharField(max_length=160, blank=True)
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-enviado_em']
        verbose_name = 'Documento do morador'
        verbose_name_plural = 'Documentos dos moradores'


class Ocupacao(models.Model):
    morador = models.ForeignKey(Morador, on_delete=models.PROTECT, related_name='ocupacoes')
    apartamento = models.ForeignKey(Apartamento, on_delete=models.PROTECT, related_name='ocupacoes')
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    dia_vencimento = models.PositiveSmallIntegerField(
        default=10, validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    valor_aluguel = models.DecimalField(max_digits=10, decimal_places=2)
    valor_mobilia = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ativa = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True)

    class Meta:
        ordering = ['-ativa', '-data_inicio']
        verbose_name = 'Ocupação'
        verbose_name_plural = 'Ocupações'

    def __str__(self):
        return f'{self.morador} — {self.apartamento}'

    @property
    def valor_total_mensal(self):
        return self.valor_aluguel + self.valor_mobilia

    @property
    def filiais_ativos(self):
        return self.membros.filter(ativa=True, data_fim__isnull=True).select_related('morador')

    @property
    def moradores_atuais(self):
        return [self.morador] + [m.morador for m in self.filiais_ativos]


class MembroOcupacao(models.Model):
    ocupacao = models.ForeignKey(Ocupacao, on_delete=models.CASCADE, related_name='membros')
    morador = models.ForeignKey(Morador, on_delete=models.PROTECT, related_name='vinculos_ocupacao')
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    ativa = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-ativa', 'morador__nome_completo']
        constraints = [
            models.UniqueConstraint(
                fields=['morador'], condition=Q(ativa=True, data_fim__isnull=True),
                name='morador_um_vinculo_filial_ativo'
            ),
            models.UniqueConstraint(
                fields=['ocupacao', 'morador'], condition=Q(ativa=True, data_fim__isnull=True),
                name='filial_unico_na_ocupacao_ativa'
            ),
        ]
        verbose_name = 'Morador filial da ocupação'
        verbose_name_plural = 'Moradores filiais das ocupações'

    def __str__(self):
        return f'{self.morador} — filial de {self.ocupacao.apartamento}'


class HistoricoResponsavelOcupacao(models.Model):
    ocupacao = models.ForeignKey(Ocupacao, on_delete=models.CASCADE, related_name='historico_responsaveis')
    morador = models.ForeignKey(Morador, on_delete=models.PROTECT, related_name='historico_responsavel')
    data_inicio = models.DateField()
    data_fim = models.DateField()
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_fim']
        verbose_name = 'Histórico de responsável'
        verbose_name_plural = 'Histórico de responsáveis'

    def __str__(self):
        return f'{self.morador} — {self.ocupacao.apartamento} ({self.data_inicio:%d/%m/%Y} a {self.data_fim:%d/%m/%Y})'


class ItemMobilia(models.Model):
    ESTADOS = [('BOM', 'Bom'), ('REGULAR', 'Regular'), ('DANIFICADO', 'Danificado')]
    apartamento = models.ForeignKey(Apartamento, on_delete=models.CASCADE, related_name='itens_mobilia')
    nome = models.CharField(max_length=120)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='BOM')
    observacoes = models.TextField(blank=True)

    class Meta:
        ordering = ['apartamento', 'nome']
        verbose_name = 'Item de mobília'
        verbose_name_plural = 'Itens de mobília'

    def __str__(self):
        return f'{self.nome} — {self.apartamento}'


class Pagamento(models.Model):
    FORMAS = [
        ('PIX', 'PIX'), ('DINHEIRO', 'Dinheiro'), ('TRANSFERENCIA', 'Transferência'),
        ('BOLETO', 'Boleto'), ('OUTRO', 'Outro'),
    ]
    ocupacao = models.ForeignKey(Ocupacao, on_delete=models.PROTECT, related_name='pagamentos')
    morador_referencia = models.ForeignKey(
        Morador, on_delete=models.PROTECT, related_name='pagamentos_referencia', null=True, blank=True,
        help_text='Responsável registrado no momento do pagamento.'
    )
    competencia = models.DateField(help_text='Use o primeiro dia do mês de referência.')
    vencimento = models.DateField()
    valor_devido = models.DecimalField(max_digits=10, decimal_places=2)
    credito_aplicado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    data_pagamento = models.DateField(null=True, blank=True)
    forma_pagamento = models.CharField(max_length=20, choices=FORMAS, blank=True)
    observacoes = models.TextField(blank=True)
    justificativa_excedente = models.TextField(blank=True)
    descricao_excedente_recibo = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-competencia', 'vencimento']
        constraints = [
            models.UniqueConstraint(fields=['ocupacao', 'competencia'], name='pagamento_unico_por_competencia')
        ]
        verbose_name = 'Pagamento'
        verbose_name_plural = 'Pagamentos'

    @property
    def valor_mensal_referencia(self):
        return self.valor_devido + self.credito_aplicado

    @property
    def saldo(self):
        return max(self.valor_devido - self.valor_pago, Decimal('0'))

    @property
    def valor_excedente(self):
        return max(self.valor_pago - self.valor_devido, Decimal('0'))

    @property
    def valor_pago_competencia(self):
        return min(self.valor_pago, self.valor_devido)

    @property
    def percentual_pago(self):
        if self.valor_devido <= 0:
            return 100
        return min(int((self.valor_pago_competencia / self.valor_devido) * 100), 100)

    @property
    def status(self):
        from django.utils import timezone
        if self.valor_pago >= self.valor_devido:
            return 'PAGO'
        if self.vencimento < timezone.localdate():
            return 'ATRASO'
        if self.valor_pago > 0:
            return 'PARCIAL'
        return 'PENDENTE'


class LancamentoPagamento(models.Model):
    ORIGENS = [
        ('ADMIN', 'Registrado pela administração'),
        ('MORADOR', 'Informado pelo morador'),
        ('LEGADO', 'Registro anterior à v0.3.4'),
    ]
    pagamento = models.ForeignKey(Pagamento, on_delete=models.CASCADE, related_name='lancamentos')
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data_pagamento = models.DateField()
    forma_pagamento = models.CharField(max_length=20, choices=Pagamento.FORMAS, blank=True)
    origem = models.CharField(max_length=20, choices=ORIGENS, default='ADMIN')
    justificativa_excedente = models.TextField(blank=True)
    descricao_excedente_recibo = models.TextField(blank=True)
    valor_excedente = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gerar_credito_proxima_competencia = models.BooleanField(default=False)
    comprovante = models.OneToOneField(
        'ComprovantePagamento', on_delete=models.SET_NULL, related_name='lancamento', null=True, blank=True
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='lancamentos_pagamento_criados',
        null=True, blank=True
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['data_pagamento', 'criado_em']
        verbose_name = 'Lançamento de pagamento'
        verbose_name_plural = 'Lançamentos de pagamentos'

    def __str__(self):
        return f'R$ {self.valor} — {self.pagamento.ocupacao} — {self.pagamento.competencia:%m/%Y}'


class AjusteCompetencia(models.Model):
    ocupacao = models.ForeignKey(Ocupacao, on_delete=models.CASCADE, related_name='ajustes_competencia')
    competencia = models.DateField()
    valor_credito = models.DecimalField(max_digits=10, decimal_places=2)
    descricao = models.TextField(blank=True)
    origem_pagamento = models.OneToOneField(
        Pagamento, on_delete=models.CASCADE, related_name='credito_gerado', null=True, blank=True
    )
    ativo = models.BooleanField(default=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='ajustes_financeiros_criados', null=True, blank=True
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-competencia', '-criado_em']
        verbose_name = 'Crédito de competência'
        verbose_name_plural = 'Créditos de competências'

    def __str__(self):
        return f'Crédito R$ {self.valor_credito} — {self.ocupacao} — {self.competencia:%m/%Y}'


class ContaImovel(models.Model):
    TIPOS = [
        ('ENERGIA', 'Energia'), ('AGUA', 'Água'), ('IPTU', 'IPTU'), ('OUTRO', 'Outro'),
    ]
    predio = models.ForeignKey(Predio, on_delete=models.CASCADE, related_name='contas')
    apartamento = models.ForeignKey(
        Apartamento, on_delete=models.CASCADE, related_name='contas', null=True, blank=True
    )
    tipo = models.CharField(max_length=20, choices=TIPOS)
    fornecedor = models.CharField(max_length=120)
    rotulo_codigo = models.CharField(max_length=80, default='Código da conta')
    codigo = models.CharField(max_length=120)
    url_portal = models.URLField(blank=True)
    observacoes = models.TextField(blank=True)
    ativa = models.BooleanField(default=True)
    ultima_verificacao = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['predio__nome', 'apartamento__numero', 'tipo']
        verbose_name = 'Conta do imóvel'
        verbose_name_plural = 'Contas dos imóveis'

    def __str__(self):
        unidade = f'Apt. {self.apartamento.numero}' if self.apartamento else 'Geral'
        return f'{self.get_tipo_display()} — {self.predio.nome} — {unidade}'


class PagamentoContaImovel(models.Model):
    conta = models.ForeignKey(ContaImovel, on_delete=models.CASCADE, related_name='pagamentos')
    competencia = models.DateField(help_text='Use o primeiro dia do mês de referência da conta.')
    valor_pago = models.DecimalField(max_digits=12, decimal_places=2)
    data_pagamento = models.DateField()
    comprovante = models.FileField(upload_to='contas/comprovantes/%Y/%m/', blank=True)
    observacoes = models.TextField(blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pagamentos_contas_criados'
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-competencia', '-data_pagamento', '-criado_em']
        verbose_name = 'Pagamento de conta do imóvel'
        verbose_name_plural = 'Pagamentos de contas dos imóveis'

    def __str__(self):
        return f'{self.conta} — {self.competencia:%m/%Y} — R$ {self.valor_pago}'


class PerfilUsuario(models.Model):
    PAPEIS = [
        ('PROPRIETARIO', 'Proprietário'),
        ('ADMIN', 'Administrador'),
        ('MORADOR', 'Morador'),
    ]
    STATUS = [
        ('PENDENTE', 'Aguardando aprovação'),
        ('ATIVO', 'Ativo'),
        ('SUSPENSO', 'Suspenso'),
        ('RECUSADO', 'Recusado'),
    ]
    DOCUMENTOS = [('RG', 'RG'), ('CNH', 'CNH')]
    TIPOS_VINCULO = [
        ('RESPONSAVEL', 'Responsável por apartamento'),
        ('FILIAL', 'Morador filial de uma ocupação existente'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil_imobiliario')
    papel = models.CharField(max_length=20, choices=PAPEIS, default='MORADOR')
    status = models.CharField(max_length=20, choices=STATUS, default='PENDENTE')
    nome_completo = models.CharField(max_length=180, blank=True)
    cpf = models.CharField(max_length=14, unique=True, null=True, blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    telefone = models.CharField(max_length=30, blank=True)
    morador = models.OneToOneField(
        Morador, on_delete=models.SET_NULL, related_name='perfil_usuario', null=True, blank=True
    )
    apartamento_solicitado = models.ForeignKey(
        Apartamento, on_delete=models.SET_NULL, related_name='perfis_solicitantes', null=True, blank=True
    )
    tipo_vinculo_solicitado = models.CharField(
        max_length=20, choices=TIPOS_VINCULO, default='RESPONSAVEL'
    )
    documento_tipo = models.CharField(max_length=10, choices=DOCUMENTOS, blank=True)
    documento_frente = models.FileField(upload_to='acessos/documentos/%Y/%m/', blank=True)
    documento_verso = models.FileField(upload_to='acessos/documentos/%Y/%m/', blank=True)
    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='acessos_aprovados', null=True, blank=True
    )
    aprovado_em = models.DateTimeField(null=True, blank=True)
    admin_acesso_todos_predios = models.BooleanField(default=False)
    predios_administrados = models.ManyToManyField(
        Predio, blank=True, related_name='administradores_permitidos'
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Perfil de acesso'
        verbose_name_plural = 'Perfis de acesso'

    def __str__(self):
        return f'{self.nome_completo or self.user.username} — {self.get_papel_display()}'

    @property
    def eh_gestor(self):
        return self.status == 'ATIVO' and self.papel in {'PROPRIETARIO', 'ADMIN'}

    @property
    def ocupacao_atual(self):
        if not self.morador_id:
            return None
        return self.morador.ocupacao_atual

    @property
    def tem_residencia(self):
        return bool(self.status == 'ATIVO' and self.morador_id and self.ocupacao_atual)


class Comunicado(models.Model):
    TIPOS = [
        ('GERAL', 'Aviso geral'),
        ('COBRANCA', 'Cobrança'),
        ('MANUTENCAO', 'Manutenção'),
        ('OUTRO', 'Outro'),
    ]
    ALCANCES = [
        ('TODOS', 'Todos os moradores'),
        ('PREDIO', 'Moradores de um prédio'),
        ('MORADOR', 'Morador específico'),
    ]
    titulo = models.CharField(max_length=160)
    mensagem = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPOS, default='GERAL')
    alcance = models.CharField(max_length=20, choices=ALCANCES, default='TODOS')
    predio = models.ForeignKey(Predio, on_delete=models.SET_NULL, null=True, blank=True, related_name='comunicados')
    morador = models.ForeignKey(Morador, on_delete=models.SET_NULL, null=True, blank=True, related_name='comunicados_diretos')
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='comunicados_criados')
    criado_em = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Comunicado'
        verbose_name_plural = 'Comunicados'

    def __str__(self):
        return self.titulo


class DestinatarioComunicado(models.Model):
    comunicado = models.ForeignKey(Comunicado, on_delete=models.CASCADE, related_name='destinatarios')
    perfil = models.ForeignKey(PerfilUsuario, on_delete=models.CASCADE, related_name='comunicados_recebidos')
    lido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['comunicado', 'perfil'], name='comunicado_destinatario_unico')
        ]
        ordering = ['-comunicado__criado_em']


class SolicitacaoManutencao(models.Model):
    CATEGORIAS = [
        ('HIDRAULICA', 'Hidráulica'),
        ('ELETRICA', 'Elétrica'),
        ('ESTRUTURAL', 'Estrutural'),
        ('MOBILIA', 'Mobília'),
        ('OUTRO', 'Outro'),
    ]
    STATUS = [
        ('ABERTA', 'Aberta'),
        ('ANALISE', 'Em análise'),
        ('AGENDADA', 'Visita agendada'),
        ('ANDAMENTO', 'Em andamento'),
        ('RESOLVIDA', 'Resolvida'),
        ('CANCELADA', 'Cancelada'),
    ]
    morador = models.ForeignKey(Morador, on_delete=models.PROTECT, related_name='solicitacoes_manutencao')
    ocupacao = models.ForeignKey(Ocupacao, on_delete=models.PROTECT, related_name='solicitacoes_manutencao')
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default='OUTRO')
    titulo = models.CharField(max_length=160)
    descricao = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS, default='ABERTA')
    data_visita = models.DateTimeField(null=True, blank=True)
    observacao_administracao = models.TextField(blank=True)
    encerrado_pelo_morador = models.BooleanField(default=False)
    justificativa_encerramento = models.TextField(blank=True)
    encerrado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Solicitação de manutenção'
        verbose_name_plural = 'Solicitações de manutenção'

    def __str__(self):
        return f'#{self.pk or "novo"} — {self.titulo}'


class AnexoManutencao(models.Model):
    solicitacao = models.ForeignKey(SolicitacaoManutencao, on_delete=models.CASCADE, related_name='anexos')
    arquivo = models.FileField(upload_to='manutencoes/%Y/%m/')
    enviado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='anexos_manutencao')
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['enviado_em']


class ComprovantePagamento(models.Model):
    STATUS = [
        ('PENDENTE', 'Aguardando confirmação'),
        ('APROVADO', 'Confirmado'),
        ('RECUSADO', 'Recusado'),
    ]
    morador = models.ForeignKey(Morador, on_delete=models.PROTECT, related_name='comprovantes_pagamento')
    ocupacao = models.ForeignKey(Ocupacao, on_delete=models.PROTECT, related_name='comprovantes_pagamento')
    competencia = models.DateField()
    valor_informado = models.DecimalField(max_digits=10, decimal_places=2)
    data_pagamento = models.DateField()
    forma_pagamento = models.CharField(max_length=20, choices=Pagamento.FORMAS, default='PIX')
    arquivo = models.FileField(upload_to='comprovantes/%Y/%m/', blank=True)
    observacoes = models.TextField(blank=True)
    justificativa_excedente = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='PENDENTE')
    analisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='comprovantes_analisados', null=True, blank=True
    )
    analisado_em = models.DateTimeField(null=True, blank=True)
    pagamento = models.ForeignKey(
        Pagamento, on_delete=models.SET_NULL, related_name='comprovantes', null=True, blank=True
    )
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-enviado_em']
        verbose_name = 'Comprovante de pagamento'
        verbose_name_plural = 'Comprovantes de pagamento'

    def __str__(self):
        return f'{self.morador} — {self.competencia:%m/%Y}'