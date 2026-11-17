from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect

from .models import PerfilUsuario, Predio


def normalizar_cpf(valor):
    return ''.join(ch for ch in (valor or '') if ch.isdigit())


def garantir_perfil(user):
    if not user or not user.is_authenticated:
        return None
    try:
        perfil = user.perfil_imobiliario
    except PerfilUsuario.DoesNotExist:
        if user.is_superuser:
            papel, status = 'PROPRIETARIO', 'ATIVO'
        elif user.is_staff:
            papel, status = 'ADMIN', 'ATIVO'
        else:
            papel, status = 'MORADOR', 'PENDENTE'
        perfil = PerfilUsuario.objects.create(
            user=user,
            papel=papel,
            status=status,
            nome_completo=user.get_full_name() or user.username,
            admin_acesso_todos_predios=bool(user.is_superuser),
        )
    else:
        if user.is_superuser and (
            perfil.papel != 'PROPRIETARIO' or perfil.status != 'ATIVO' or not perfil.admin_acesso_todos_predios
        ):
            perfil.papel = 'PROPRIETARIO'
            perfil.status = 'ATIVO'
            perfil.admin_acesso_todos_predios = True
            perfil.save(update_fields=['papel', 'status', 'admin_acesso_todos_predios'])
    return perfil


def predios_permitidos(perfil, incluir_inativos=True):
    qs = Predio.objects.all()
    if not incluir_inativos:
        qs = qs.filter(ativo=True)
    if not perfil or perfil.status != 'ATIVO':
        return qs.none()
    if perfil.papel == 'PROPRIETARIO':
        return qs
    if perfil.papel == 'ADMIN':
        if perfil.admin_acesso_todos_predios:
            return qs
        return qs.filter(pk__in=perfil.predios_administrados.values('pk'))
    return qs.none()


def gestor_pode_predio(perfil, predio_id):
    if not perfil or not perfil.eh_gestor:
        return False
    if perfil.papel == 'PROPRIETARIO' or perfil.admin_acesso_todos_predios:
        return True
    return perfil.predios_administrados.filter(pk=predio_id).exists()


def gestor_pode_morador(perfil, morador):
    if not perfil or not perfil.eh_gestor:
        return False
    if perfil.papel == 'PROPRIETARIO' or perfil.admin_acesso_todos_predios:
        return True
    ids = perfil.predios_administrados.values_list('pk', flat=True)
    return (
        morador.ocupacoes.filter(apartamento__predio_id__in=ids).exists()
        or morador.vinculos_ocupacao.filter(ocupacao__apartamento__predio_id__in=ids).exists()
        or morador.historico_responsavel.filter(ocupacao__apartamento__predio_id__in=ids).exists()
    )


def gestor_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        perfil = garantir_perfil(request.user)
        if perfil and perfil.eh_gestor:
            return view_func(request, *args, **kwargs)
        messages.error(request, 'Seu usuário não possui permissão para acessar essa área.')
        return redirect('dashboard')
    return wrapper


def proprietario_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        perfil = garantir_perfil(request.user)
        if perfil and perfil.status == 'ATIVO' and perfil.papel == 'PROPRIETARIO':
            return view_func(request, *args, **kwargs)
        messages.error(request, 'Somente o proprietário pode realizar esta alteração.')
        return redirect('usuarios_acessos')
    return wrapper


def morador_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        perfil = garantir_perfil(request.user)
        if perfil and perfil.status == 'ATIVO' and perfil.morador_id and perfil.ocupacao_atual:
            return view_func(request, *args, **kwargs)
        return redirect('estado_acesso')
    return wrapper
