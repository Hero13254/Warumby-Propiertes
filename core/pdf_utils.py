from io import BytesIO
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


MESES = [
    'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
]


def formatar_brl(valor):
    bruto = f'{valor:,.2f}'
    return bruto.replace(',', 'X').replace('.', ',').replace('X', '.')


def gerar_recibo_pdf(*, morador, predio, apartamento, competencia, valor_pago,
                      valor_total, saldo, data_pagamento, forma_pagamento='', cpf='', endereco='',
                      credito_aplicado=0, valor_excedente=0, descricao_excedente='', lancamentos=None):
    """Gera recibo consolidado da competência, incluindo parcelas e valores adicionais."""
    lancamentos = lancamentos or []
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=2.0 * cm, leftMargin=2.0 * cm,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        title='Recibo de aluguel', author='Warumby Properties',
    )
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle('TituloRecibo', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=18, leading=22, alignment=TA_CENTER, spaceAfter=18)
    corpo = ParagraphStyle('CorpoRecibo', parent=styles['BodyText'], fontName='Helvetica', fontSize=11.2, leading=17, alignment=TA_LEFT, spaceAfter=9)
    centro = ParagraphStyle('CentroRecibo', parent=corpo, alignment=TA_CENTER, fontSize=10)
    destaque = ParagraphStyle('DestaqueRecibo', parent=corpo, fontName='Helvetica-Bold', fontSize=11.5)
    pequeno = ParagraphStyle('PequenoRecibo', parent=corpo, fontSize=9.5, leading=13)

    comp = f'{MESES[competencia.month - 1]} de {competencia.year}'
    data_txt = data_pagamento.strftime('%d/%m/%Y') if data_pagamento else 'não informada'
    forma_txt = forma_pagamento or 'não informada'
    cpf_txt = f', CPF {escape(str(cpf))}' if cpf else ''
    endereco_txt = f', situado em {escape(str(endereco))}' if endereco else ''
    valor_devido_em_dinheiro = max(valor_total - credito_aplicado, 0)
    valor_aluguel_recebido = min(valor_pago, valor_devido_em_dinheiro)

    if valor_excedente > 0:
        texto_recebimento = (
            f'Recebi de <b>{escape(str(morador))}</b>{cpf_txt} o total de <b>R$ {formatar_brl(valor_pago)}</b>. '
            f'Desse total, <b>R$ {formatar_brl(valor_aluguel_recebido)}</b> foi destinado à competência de '
            f'<b>{escape(comp)}</b> do <b>Apartamento {escape(str(apartamento))}</b>, no imóvel '
            f'<b>{escape(str(predio))}</b>{endereco_txt}. O valor adicional de '
            f'<b>R$ {formatar_brl(valor_excedente)}</b> é discriminado separadamente abaixo.'
        )
    else:
        texto_recebimento = (
            f'Recebi de <b>{escape(str(morador))}</b>{cpf_txt} o total confirmado de '
            f'<b>R$ {formatar_brl(valor_pago)}</b>, referente à competência de <b>{escape(comp)}</b> do '
            f'<b>Apartamento {escape(str(apartamento))}</b>, no imóvel <b>{escape(str(predio))}</b>{endereco_txt}.'
        )

    story = [Paragraph('RECIBO DE ALUGUEL', titulo), Paragraph(texto_recebimento, corpo)]
    dados = [
        ['Competência', comp],
        ['Valor mensal do apartamento', f'R$ {formatar_brl(valor_total)}'],
        ['Crédito anterior aplicado', f'R$ {formatar_brl(credito_aplicado)}' if credito_aplicado else '—'],
        ['Valor devido nesta competência', f'R$ {formatar_brl(valor_devido_em_dinheiro)}'],
        ['Valor destinado à competência', f'R$ {formatar_brl(valor_aluguel_recebido)}'],
        ['Total recebido', f'R$ {formatar_brl(valor_pago)}'],
        ['Saldo da competência', f'R$ {formatar_brl(saldo)}'],
        ['Valor adicional / excedente', f'R$ {formatar_brl(valor_excedente)}' if valor_excedente else '—'],
    ]
    tabela = Table(dados, colWidths=[6.3 * cm, 8.9 * cm], hAlign='LEFT')
    tabela.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'), ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10.2), ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F4F6F8')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D9DEE5')), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    story.extend([Spacer(1, 8), tabela, Spacer(1, 12)])

    if lancamentos and len(lancamentos) > 1:
        story.append(Paragraph('<b>Lançamentos confirmados nesta competência</b>', corpo))
        linhas = [['Data', 'Forma', 'Valor']]
        for item in lancamentos:
            linhas.append([
                item.data_pagamento.strftime('%d/%m/%Y') if item.data_pagamento else '—',
                item.get_forma_pagamento_display() if item.forma_pagamento else '—',
                f'R$ {formatar_brl(item.valor)}',
            ])
        t = Table(linhas, colWidths=[4.8 * cm, 5.2 * cm, 5.2 * cm], hAlign='LEFT')
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9.4), ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F4F6F8')),
            ('GRID', (0, 0), (-1, -1), 0.45, colors.HexColor('#D9DEE5')), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.extend([t, Spacer(1, 12)])

    if valor_excedente > 0:
        descricao = escape(str(descricao_excedente or 'Valor adicional informado pela administração.'))
        story.append(Paragraph(f'<b>Valor adicional:</b> R$ {formatar_brl(valor_excedente)} — {descricao}', pequeno))
    if credito_aplicado > 0:
        story.append(Paragraph(
            f'Foi aplicado crédito anterior de <b>R$ {formatar_brl(credito_aplicado)}</b> para reduzir o valor devido nesta competência.',
            pequeno,
        ))
    if saldo > 0:
        story.append(Paragraph(f'<b>Pagamento parcial.</b> Permanece saldo de <b>R$ {formatar_brl(saldo)}</b>.', destaque))
    else:
        story.append(Paragraph('A obrigação mensal desta competência encontra-se quitada no sistema.', corpo))

    story.extend([
        Spacer(1, 22), Paragraph(f'Maceió/AL, {escape(data_txt)}.', centro), Spacer(1, 58),
        HRFlowable(width='65%', thickness=0.8, color=colors.black, hAlign='CENTER'), Spacer(1, 6),
        Paragraph('Assinatura do responsável pelo recebimento', centro),
    ])
    doc.build(story)
    return buffer.getvalue()


def gerar_comprovante_residencia_pagamentos_pdf(*, morador, cpf, predio, endereco,
                                                   apartamento, data_inicio, pagamentos,
                                                   data_emissao, valor_apartamento_atual=0):
    """Gera declaração de residência com o histórico recente de pagamentos confirmados."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=1.6 * cm, leftMargin=1.6 * cm,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        title='Comprovante de residência e pagamentos', author='Warumby Properties',
    )
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle('TituloDeclaracao', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=16.5, leading=20, alignment=TA_CENTER, spaceAfter=16)
    corpo = ParagraphStyle('CorpoDeclaracao', parent=styles['BodyText'], fontName='Helvetica', fontSize=10.8, leading=16, alignment=TA_LEFT, spaceAfter=9)
    centro = ParagraphStyle('CentroDeclaracao', parent=corpo, alignment=TA_CENTER, fontSize=9.7)
    celula = ParagraphStyle('Celula', parent=corpo, fontSize=8.4, leading=10.5, spaceAfter=0)

    cpf_txt = f', CPF {escape(str(cpf))}' if cpf else ''
    endereco_txt = escape(str(endereco or 'endereço cadastrado no sistema'))
    inicio_txt = data_inicio.strftime('%d/%m/%Y') if data_inicio else 'data não informada'
    emissao_txt = data_emissao.strftime('%d/%m/%Y')
    quitados = [p for p in pagamentos if p.valor_pago >= p.valor_devido]
    mais_recente_quitada = quitados[0].competencia if quitados else None
    competencia_txt = (
        f'{MESES[mais_recente_quitada.month - 1]} de {mais_recente_quitada.year}'
        if mais_recente_quitada else 'nenhuma competência integralmente quitada'
    )

    story = [
        Paragraph('DECLARAÇÃO DE RESIDÊNCIA E PAGAMENTOS', titulo),
        Paragraph(
            f'Para fins de comprovação, declaramos que <b>{escape(str(morador))}</b>{cpf_txt} '
            f'encontra-se cadastrado(a) como ocupante do <b>Apartamento {escape(str(apartamento))}</b>, '
            f'no imóvel <b>{escape(str(predio))}</b>, localizado em <b>{endereco_txt}</b>, desde <b>{inicio_txt}</b>.',
            corpo,
        ),
        Paragraph(
            f'O valor mensal atualmente cadastrado para o apartamento é <b>R$ {formatar_brl(valor_apartamento_atual)}</b>. '
            f'A competência mais recente integralmente quitada registrada no sistema é <b>{escape(competencia_txt)}</b>. '
            f'A tabela abaixo discrimina os pagamentos confirmados, sem incorporar valores excedentes ao aluguel mensal.',
            corpo,
        ),
    ]

    dados = [[
        Paragraph('<b>Competência</b>', celula), Paragraph('<b>Aluguel</b>', celula),
        Paragraph('<b>Pago p/ competência</b>', celula), Paragraph('<b>Saldo</b>', celula),
        Paragraph('<b>Excedente e justificativa</b>', celula),
    ]]
    for pagamento in pagamentos:
        recebido_competencia = min(pagamento.valor_pago, pagamento.valor_devido)
        excedente = pagamento.valor_excedente
        extra = '—'
        if excedente > 0:
            descricao = pagamento.descricao_excedente_recibo or pagamento.justificativa_excedente or 'Valor adicional registrado.'
            extra = f'R$ {formatar_brl(excedente)} — {escape(str(descricao))}'
        dados.append([
            Paragraph(pagamento.competencia.strftime('%m/%Y'), celula),
            Paragraph(f'R$ {formatar_brl(pagamento.valor_mensal_referencia)}', celula),
            Paragraph(f'R$ {formatar_brl(recebido_competencia)}', celula),
            Paragraph(f'R$ {formatar_brl(pagamento.saldo)} ({escape(pagamento.status)})', celula),
            Paragraph(extra, celula),
        ])

    tabela = Table(dados, colWidths=[2.4 * cm, 2.8 * cm, 3.4 * cm, 3.0 * cm, 5.6 * cm], hAlign='LEFT', repeatRows=1)
    tabela.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 8.4),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F4F6F8')), ('GRID', (0, 0), (-1, -1), 0.45, colors.HexColor('#D9DEE5')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.extend([
        Spacer(1, 7), tabela, Spacer(1, 14),
        Paragraph(
            'Valores adicionais aparecem separados do aluguel e acompanhados da justificativa registrada pela administração. '
            'Este documento reflete os dados existentes no Warumby Properties até a data de emissão.',
            corpo,
        ),
        Spacer(1, 22), Paragraph(f'Maceió/AL, {emissao_txt}.', centro), Spacer(1, 58),
        HRFlowable(width='65%', thickness=0.8, color=colors.black, hAlign='CENTER'), Spacer(1, 6),
        Paragraph('Assinatura do responsável pela administração', centro),
    ])
    doc.build(story)
    return buffer.getvalue()


def gerar_relatorio_financeiro_pdf(*, competencia_inicio, competencia_fim, escopo_descricao,
                                    linhas, totais, data_emissao):
    """Relatório financeiro proprietário: receitas de aluguel, despesas pagas e resultado líquido."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=1.25 * cm, leftMargin=1.25 * cm,
        topMargin=1.4 * cm, bottomMargin=1.4 * cm,
        title='Relatório financeiro', author='Warumby Properties',
    )
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle('TituloFinanceiro', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=16, leading=19, alignment=TA_CENTER, spaceAfter=10)
    corpo = ParagraphStyle('CorpoFinanceiro', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.5, leading=13, spaceAfter=7)
    pequeno = ParagraphStyle('PequenoFinanceiro', parent=corpo, fontSize=7.4, leading=9.2, spaceAfter=0)
    centro = ParagraphStyle('CentroFinanceiro', parent=corpo, alignment=TA_CENTER)

    periodo = f'{competencia_inicio:%m/%Y} a {competencia_fim:%m/%Y}'
    story = [
        Paragraph('RELATÓRIO FINANCEIRO — RESULTADO LÍQUIDO', titulo),
        Paragraph(f'<b>Período:</b> {periodo}<br/><b>Abrangência:</b> {escape(str(escopo_descricao))}', corpo),
        Paragraph(
            'Receita confirmada considera o valor efetivamente destinado às competências de aluguel. '
            'Despesas correspondem às contas do imóvel registradas como pagas na Central de Contas. '
            'Valores excedentes de aluguel aparecem separados para evitar dupla contagem de créditos antecipados.',
            corpo,
        ),
    ]

    dados = [[
        Paragraph('<b>Mês</b>', pequeno), Paragraph('<b>Unidade</b>', pequeno),
        Paragraph('<b>Previsto</b>', pequeno), Paragraph('<b>Receita</b>', pequeno),
        Paragraph('<b>Despesas</b>', pequeno), Paragraph('<b>Resultado</b>', pequeno),
        Paragraph('<b>Pendente</b>', pequeno), Paragraph('<b>Excedente</b>', pequeno),
    ]]
    for linha in linhas:
        resultado = linha.get('resultado', 0)
        dados.append([
            Paragraph(linha['competencia'].strftime('%m/%Y'), pequeno),
            Paragraph(escape(str(linha['unidade'])), pequeno),
            Paragraph(f"R$ {formatar_brl(linha.get('previsto', 0))}", pequeno),
            Paragraph(f"R$ {formatar_brl(linha.get('receita', 0))}", pequeno),
            Paragraph(f"R$ {formatar_brl(linha.get('despesas', 0))}", pequeno),
            Paragraph(f"R$ {formatar_brl(resultado)}", pequeno),
            Paragraph(f"R$ {formatar_brl(linha.get('pendente', 0))}", pequeno),
            Paragraph(f"R$ {formatar_brl(linha.get('excedente', 0))}", pequeno),
        ])

    tabela = Table(dados, colWidths=[1.45*cm, 3.4*cm, 2.05*cm, 2.05*cm, 2.05*cm, 2.05*cm, 2.05*cm, 2.05*cm], repeatRows=1, hAlign='LEFT')
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F4F6F8')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.35, colors.HexColor('#D9DEE5')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 3), ('RIGHTPADDING', (0,0), (-1,-1), 3),
        ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.extend([tabela, Spacer(1, 12)])

    resumo = [
        ['Aluguel previsto', f"R$ {formatar_brl(totais.get('previsto', 0))}"],
        ['Receita de aluguel confirmada', f"R$ {formatar_brl(totais.get('receita', 0))}"],
        ['Despesas pagas', f"R$ {formatar_brl(totais.get('despesas', 0))}"],
        ['Resultado líquido', f"R$ {formatar_brl(totais.get('resultado', 0))}"],
        ['Saldo pendente', f"R$ {formatar_brl(totais.get('pendente', 0))}"],
        ['Valores excedentes recebidos', f"R$ {formatar_brl(totais.get('excedente', 0))}"],
    ]
    t_resumo = Table(resumo, colWidths=[8.5*cm, 6.0*cm], hAlign='LEFT')
    t_resumo.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#F4F6F8')),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.45, colors.HexColor('#D9DEE5')),
        ('FONTSIZE', (0,0), (-1,-1), 9.5),
        ('LEFTPADDING', (0,0), (-1,-1), 7), ('RIGHTPADDING', (0,0), (-1,-1), 7),
        ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.extend([
        Paragraph('<b>Resumo do período</b>', corpo), t_resumo, Spacer(1, 14),
        Paragraph(
            'Resultado líquido = receita de aluguel confirmada − despesas pagas registradas. '
            'Despesas gerais do prédio não são rateadas automaticamente entre apartamentos; em relatórios de apartamentos específicos, '
            'entram apenas contas vinculadas diretamente às unidades selecionadas.',
            corpo,
        ),
        Paragraph(f'Emitido em {data_emissao:%d/%m/%Y} pelo Warumby Properties.', centro),
    ])
    doc.build(story)
    return buffer.getvalue()


def gerar_comprovante_pagamentos_apartamento_pdf(*, predio, endereco, apartamento,
                                                  competencia_inicio, competencia_fim,
                                                  pagamentos, data_emissao):
    """Comprovante/extrato consolidado de várias competências de um apartamento."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=1.4*cm, leftMargin=1.4*cm,
        topMargin=1.6*cm, bottomMargin=1.6*cm,
        title='Comprovante consolidado de pagamentos', author='Warumby Properties',
    )
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle('TituloConsolidado', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=16, leading=19, alignment=TA_CENTER, spaceAfter=12)
    corpo = ParagraphStyle('CorpoConsolidado', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.6, leading=13, spaceAfter=7)
    cel = ParagraphStyle('CelConsolidado', parent=corpo, fontSize=7.7, leading=9.5, spaceAfter=0)
    centro = ParagraphStyle('CentroConsolidado', parent=corpo, alignment=TA_CENTER)

    story = [
        Paragraph('COMPROVANTE CONSOLIDADO DE PAGAMENTOS', titulo),
        Paragraph(
            f'<b>Imóvel:</b> {escape(str(predio))} — Apartamento {escape(str(apartamento))}<br/>'
            f'<b>Endereço:</b> {escape(str(endereco or "não informado"))}<br/>'
            f'<b>Período:</b> {competencia_inicio:%m/%Y} a {competencia_fim:%m/%Y}',
            corpo,
        ),
    ]
    dados = [[
        Paragraph('<b>Competência</b>', cel), Paragraph('<b>Responsável registrado</b>', cel),
        Paragraph('<b>Mensal</b>', cel), Paragraph('<b>Crédito</b>', cel),
        Paragraph('<b>Pago</b>', cel), Paragraph('<b>Saldo</b>', cel),
        Paragraph('<b>Datas / parcelas</b>', cel),
    ]]
    total_pago = 0
    for pagamento in pagamentos:
        morador = pagamento.morador_referencia or pagamento.ocupacao.morador
        nome = morador.nome_completo if morador else 'Morador não identificado'
        lancamentos = list(pagamento.lancamentos.order_by('data_pagamento', 'criado_em'))
        if lancamentos:
            parcelas = '<br/>'.join(
                f'{l.data_pagamento:%d/%m/%Y}: R$ {formatar_brl(l.valor)}' for l in lancamentos
            )
        elif pagamento.data_pagamento:
            parcelas = f'{pagamento.data_pagamento:%d/%m/%Y}: R$ {formatar_brl(pagamento.valor_pago)}'
        else:
            parcelas = '—'
        total_pago += pagamento.valor_pago_competencia
        dados.append([
            Paragraph(pagamento.competencia.strftime('%m/%Y'), cel),
            Paragraph(escape(str(nome)), cel),
            Paragraph(f'R$ {formatar_brl(pagamento.valor_mensal_referencia)}', cel),
            Paragraph(f'R$ {formatar_brl(pagamento.credito_aplicado)}', cel),
            Paragraph(f'R$ {formatar_brl(pagamento.valor_pago_competencia)}', cel),
            Paragraph(f'R$ {formatar_brl(pagamento.saldo)}', cel),
            Paragraph(parcelas, cel),
        ])
    if not pagamentos:
        dados.append([Paragraph('Nenhum pagamento confirmado no período.', cel), '', '', '', '', '', ''])

    tabela = Table(dados, colWidths=[1.7*cm, 4.2*cm, 2.25*cm, 1.9*cm, 2.15*cm, 2.05*cm, 4.0*cm], repeatRows=1, hAlign='LEFT')
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F4F6F8')),
        ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor('#D9DEE5')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('SPAN', (0,1), (-1,1)) if not pagamentos else ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 4), ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.extend([
        tabela, Spacer(1, 12),
        Paragraph(f'<b>Total destinado às competências no período:</b> R$ {formatar_brl(total_pago)}', corpo),
        Paragraph(
            'Este documento consolida os pagamentos confirmados no Warumby Properties para a unidade e período indicados. '
            'Valores excedentes destinados a competências futuras não são somados novamente como aluguel do mês de origem.',
            corpo,
        ),
        Spacer(1, 18), Paragraph(f'Emitido em {data_emissao:%d/%m/%Y}.', centro),
    ])
    doc.build(story)
    return buffer.getvalue()