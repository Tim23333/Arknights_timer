from tools.trace_audit.chapter08_arithmetic_v2 import supported
def test_unknown_expression_and_custom_numeric_rules_never_autogreen():
 assert not supported({'id':'x','kind':'rule','implementation':{'type':'expression','expression':'inputs.custom.magic'}})
 assert not supported({'id':'x','kind':'rule','numeric':{'backend':'decimal','rounding':'floor'},'implementation':{'type':'provider','provider':'reference.c8.dynamic_buff_rate'}})
