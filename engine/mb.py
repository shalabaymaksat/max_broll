"""max_broll — plan.py ішінде қолданылатын оқиға (event) конструкторлары.

    from mb import B, B2, BOARD, I, TERM

Әр оқиға айтылған СӨЗГЕ байланады (сөз түбірі, кіші әріп). Оқиғалар видеодағы айтылу ретімен
жазылады: іздеу алдыңғы табылған сөзден кейін жалғасады. Нақты уақыт керек болса — at=секунд.
"""


def B(word, media, dur=None, src_in=0.0, until=None, at=None, fit='cover'):
    """Сплит: жоғарғы жартыда B-roll (1080×960), төменгі жартыда спикер. media — mp4/mov/jpg/png."""
    return dict(kind='split', word=word, media=[media], dur=dur, src_in=[src_in], until=until, at=at, fit=fit)


def B2(word, media_top, media_bot, dur=None, src_in=(0.0, 0.0), until=None, at=None):
    """Сплит, жоғарғы жартыда екі B-roll бір-бірінің үстінде (1080×476 + 1080×476)."""
    return dict(kind='split2', word=word, media=[media_top, media_bot], dur=dur, src_in=list(src_in),
                until=until, at=at, fit='cover')


def I(word, label, media=None, hl=False, src_in=0.0, at=None):
    """BOARD тізімінің бір жолы (таблетка). hl=True — алтын түспен белгіленеді (басты жауап)."""
    return dict(word=word, label=label, media=media, hl=hl, src_in=src_in, at=at)


def BOARD(word, title, items, until=None, at=None, hold=1.6):
    """Блюр + күңгірт спикер үстінде алтын CAPS тақырып + айтылған сайын шығатын таблеткалар.
    Таблеткада media болса — жоғарыда дөңгелек бұрышты сурет-карточка (соңғы шыққан жолдың медиасы)."""
    return dict(kind='board', word=word, title=title, items=items, until=until, at=at, hold=hold)


def TERM(word, text, then=(), until=None, at=None, hold=1.4):
    """Блюр + күңгірт спикер үстінде үлкен алтын термин (BRAND STORYTELLING, DIFFERENTIATION).
    then=[('сөз', 'ЕКІНШІ ТЕРМИН'), …] — астынан ақ түспен қосылады."""
    return dict(kind='term', word=word, text=text, then=list(then), until=until, at=at, hold=hold)
