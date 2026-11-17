from django.contrib import admin
from .models import (
    AjusteCompetencia,
    AnexoManutencao,
    Apartamento,
    Comunicado,
    ComprovantePagamento,
    ContaImovel,
    DestinatarioComunicado,
    DocumentoMorador,
    HistoricoResponsavelOcupacao,
    ItemMobilia,
    MembroOcupacao,
    Morador,
    LancamentoPagamento,
    Ocupacao,
    Pagamento,
    PagamentoContaImovel,
    PerfilUsuario,
    Predio,
    SolicitacaoManutencao,
)

admin.site.site_header = 'Warumby Properties — Administração técnica'
admin.site.site_title = 'Warumby Properties'
admin.site.index_title = 'Cadastros'


@admin.register(Predio)
class PredioAdmin(admin.ModelAdmin):
    list_display = ('nome', 'endereco', 'ativo')
    search_fields = ('nome', 'endereco')


@admin.register(Apartamento)
class ApartamentoAdmin(admin.ModelAdmin):
    list_display = ('predio', 'numero', 'andar', 'valor_aluguel_base', 'mobiliado', 'ativo')
    list_filter = ('predio', 'mobiliado', 'ativo')
    search_fields = ('numero', 'predio__nome')


@admin.register(Morador)
class MoradorAdmin(admin.ModelAdmin):
    list_display = ('nome_completo', 'cpf', 'telefone', 'ativo')
    search_fields = ('nome_completo', 'cpf', 'rg', 'telefone')


@admin.register(Ocupacao)
class OcupacaoAdmin(admin.ModelAdmin):
    list_display = ('morador', 'apartamento', 'data_inicio', 'data_fim', 'dia_vencimento', 'ativa')
    list_filter = ('ativa', 'apartamento__predio')


@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = ('ocupacao', 'competencia', 'vencimento', 'valor_devido', 'valor_pago', 'data_pagamento')
    list_filter = ('forma_pagamento', 'ocupacao__apartamento__predio')


@admin.register(ContaImovel)
class ContaImovelAdmin(admin.ModelAdmin):
    list_display = ('predio', 'apartamento', 'tipo', 'fornecedor', 'codigo', 'ativa')
    list_filter = ('tipo', 'fornecedor', 'predio', 'ativo')


@admin.register(PagamentoContaImovel)
class PagamentoContaImovelAdmin(admin.ModelAdmin):
    list_display = ('conta', 'competencia', 'valor_pago', 'data_pagamento', 'criado_por')
    list_filter = ('conta__tipo', 'conta__predio', 'competencia')

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'nome_completo', 'papel', 'status', 'morador', 'apartamento_solicitado')
    list_filter = ('papel', 'status')
    search_fields = ('user__username', 'nome_completo', 'cpf', 'morador__nome_completo')


@admin.register(Comunicado)
class ComunicadoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo', 'alcance', 'criado_por', 'criado_em', 'ativo')
    list_filter = ('tipo', 'alcance', 'ativo')

@admin.register(SolicitacaoManutencao)
class SolicitacaoManutencaoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'morador', 'ocupacao', 'categoria', 'status', 'criado_em')
    list_filter = ('categoria', 'status')


@admin.register(ComprovantePagamento)
class ComprovantePagamentoAdmin(admin.ModelAdmin):
    list_display = ('morador', 'competencia', 'valor_informado', 'status', 'enviado_em')
    list_filter = ('status', 'forma_pagamento')


admin.site.register(DocumentoMorador)
admin.site.register(ItemMobilia)
admin.site.register(DestinatarioComunicado)
admin.site.register(AnexoManutencao)
admin.site.register(MembroOcupacao)
admin.site.register(HistoricoResponsavelOcupacao)
admin.site.register(AjusteCompetencia)
admin.site.register(LancamentoPagamento)
