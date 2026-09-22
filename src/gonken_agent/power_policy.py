"""Single fixed policy payload shared by installation and standalone removal."""
RULE_NAME='49-gonken-power.rules'
RULE='''// Managed by GonKen; no shell authority and no inhibitor bypass.
polkit.addRule(function(action, subject) {
    if (subject.user === "gonken-agent" &&
        (action.id === "org.freedesktop.login1.reboot" ||
         action.id === "org.freedesktop.login1.reboot-multiple-sessions" ||
         action.id === "org.freedesktop.login1.power-off" ||
         action.id === "org.freedesktop.login1.power-off-multiple-sessions")) {
        return polkit.Result.YES;
    }
});
'''

