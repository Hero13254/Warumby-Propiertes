from .auth_utils import garantir_perfil


def perfil_usuario(request):
    if not request.user.is_authenticated:
        return {'perfil_usuario': None, 'notificacoes_nao_lidas': 0}
    perfil = garantir_perfil(request.user)
    nao_lidas = 0
    if perfil and perfil.status == 'ATIVO' and perfil.morador_id:
        nao_lidas = perfil.comunicados_recebidos.filter(lido_em__isnull=True, comunicado__ativo=True).count()
    return {'perfil_usuario': perfil, 'notificacoes_nao_lidas': nao_lidas}
