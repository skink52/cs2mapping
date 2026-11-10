# sourced by build_all.sh / deploy.sh: the same names as names.py
export IF_ARENA="${IF_ARENA:-dunes}"
eval "$(python tools/names.py 2>/dev/null; python -c "import sys; sys.path.insert(0,'tools'); import names as n; print('NAME=%s; MAP=%s; ADDON=%s; TITLE=\"%s\"' % (n.NAME, n.MAP, n.ADDON, n.TITLE))")"
