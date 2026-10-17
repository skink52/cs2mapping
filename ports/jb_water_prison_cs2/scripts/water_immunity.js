import { Instance } from "cs_script/point_script";

Instance.OnScriptInput("water_immune_on", ({ activator }) => {
    if (activator) activator.SetEntityName("waterimmune");
});

Instance.OnScriptInput("water_immune_off", ({ activator }) => {
    if (activator) activator.SetEntityName("");
});