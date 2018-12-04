
from ryu.lib.ovs import vsctl

OVSDB_ADDR = 'tcp:127.0.0.1:6640'
ovs_vsctl = vsctl.VSCtl(OVSDB_ADDR)

# Equivalent to
# $ ovs-vsctl show
command = vsctl.VSCtlCommand('show')
ovs_vsctl.run_command([command])
print(command)
# >>> VSCtlCommand(args=[],command='show',options=[],result='830d781f-c3c8-4b4f-837e-106e1b33d058\n    ovs_version: "2.8.90"\n')

# Equivalent to
# $ ovs-vsctl list Port s1-eth1
command = vsctl.VSCtlCommand('list', ('Port', 's1-eth1'))
ovs_vsctl.run_command([command])
print(command)
# >>> VSCtlCommand(args=('Port', 's1-eth1'),command='list',options=[],result=[<ovs.db.idl.Row object at 0x7f525fb682e8>])
print(command.result[0].name)
# >>> s1-eth1

