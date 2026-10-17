import { Instance } from "cs_script/point_script";

// ---- Settings ---------------------------------------------------------
// The code, one number per press. Change this to whatever you want.
const CODE = [4, 8, 2, 9, 1, 3, 7];

// If nobody presses a button for this many seconds, a half-entered code is wiped.
const RESET_AFTER = 10;

// Entity names (unchanged from your existing map)
const ACCEPT_SOUND = "keypad_%i_accept";
const REJECT_SOUND = "keypad_%i_reject";
const RED_LIGHT = "keypad_%i_redlight";
const GREEN_LIGHT = "keypad_%i_greenlight";
const VENT = "secretvent";
// Buttons must be named 0button, 1button ... 9button

// Prints what the script is doing to the console. Set to false when it works.
const DEBUG = false;
// -----------------------------------------------------------------------

function log(text) {
    if (DEBUG) Instance.Msg(`keypad: ${text}`);
}

let entered = 0;        // how many digits have been pressed this attempt
let allCorrect = true;  // has every digit so far matched?
let lastPress = 0;      // game time of the last press
let ventOpened = false; // vent only opens once, like the old logic_case

function fire(name, input, delay = 0) {
    const count = Instance.FindEntitiesByName(name).length;
    log(`fire ${input} on "${name}" (delay ${delay}) - ${count} matching entities`);
    Instance.EntFireAtName({ name, input, delay });
}

function resetAttempt() {
    entered = 0;
    allCorrect = true;
}

function success() {
    fire(ACCEPT_SOUND, "PlaySound");
    fire(GREEN_LIGHT, "Enable");
    fire(GREEN_LIGHT, "Disable", 2);
    if (!ventOpened) {
        ventOpened = true;
        fire(VENT, "Open");
    }
}

function failure() {
    fire(REJECT_SOUND, "PlaySound");
    fire(RED_LIGHT, "Enable");
    fire(RED_LIGHT, "Disable", 1);
}

function press(digit) {
    const now = Instance.GetGameTime();

    // Abandoned attempt? Start fresh.
    if (entered > 0 && now - lastPress > RESET_AFTER) {
        resetAttempt();
    }
    lastPress = now;

    if (digit !== CODE[entered]) {
        allCorrect = false;
    }
    entered++;
    log(`pressed ${digit} (${entered}/${CODE.length}), all correct so far: ${allCorrect}`);

    // No feedback until the last digit, so nobody can guess it one digit at a time.
    if (entered < CODE.length) return;

    log(allCorrect ? "code correct" : "code wrong");
    if (allCorrect) {
        success();
    } else {
        failure();
    }
    resetAttempt();
}

// Buttons and other map entities are re-created at the start of every round, so a
// hook made once at load would point at dead entities. Like the other scripts in
// this map, re-hook on every round start (after a short delay) and on hot reload.
let hooks = [];

function hookButtons() {
    for (const id of hooks) {
        try { Instance.DisconnectOutput(id); } catch (error) { /* already gone */ }
    }
    hooks = [];

    for (let digit = 0; digit <= 9; digit++) {
        const name = `${digit}button`;
        const buttons = Instance.FindEntitiesByName(name);
        if (buttons.length === 0) {
            Instance.Msg(`keypad: could not find a button named ${name}`);
            continue;
        }
        for (const button of buttons) {
            const id = Instance.ConnectOutput(button, "OnPressed", () => press(digit));
            if (id !== undefined) hooks.push(id);
        }
    }
    Instance.Msg(`keypad: ready - hooked ${hooks.length} button outputs`);
}

function start() {
    resetAttempt();
    ventOpened = false; // the vent is a fresh entity each round
    hookButtons();
}

Instance.OnActivate(start);
Instance.OnScriptReload({ after: start });
Instance.OnRoundStart(() => {
    resetAttempt();
    Instance.Delay(0.5).then(start);
});

// Console tests (need sv_cheats 1). They skip the buttons entirely, so they show
// whether the sounds, lights and vent respond when fired from the script.
Instance.RegisterCheatCommand("keypad_test_accept", () => success());
Instance.RegisterCheatCommand("keypad_test_reject", () => failure());