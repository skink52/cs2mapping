import { Instance } from "cs_script/point_script";

Instance.OnScriptInput("GiveHugeHealth", ({ activator }) => {
    if (!activator) {
        return;
    }

    activator.SetMaxHealth(1000);
    activator.SetHealth(1000);
});