import { useCallback, useEffect, useState } from "react";
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogContentText,
  DialogTitle, IconButton, Stack, TextField, Typography,
} from "@mui/material";
import PeopleRoundedIcon from "@mui/icons-material/PeopleRounded";
import BrushRoundedIcon from "@mui/icons-material/BrushRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import { UserProfile, UsersResponse, createUser, deleteUser, getUsers, signInUser, updateUser } from "../api";
import Avatar from "./Avatar";
import AvatarEditor from "./AvatarEditor";
import Field from "./Field";
import SettingsSection from "./SettingsSection";
import { RADIUS } from "../theme";

/**
 * Who uses this unit.
 *
 * Full sign-in belongs here rather than on the panel: choosing a name with
 * a joystick is miserable, and this page is already open on something with
 * a keyboard. The matrix gets the four-digit PIN, which a thumb can manage.
 */
export default function UsersPanel() {
  const [data, setData] = useState<UsersResponse | null>(null);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [drawing, setDrawing] = useState<UserProfile | null>(null);
  const [removing, setRemoving] = useState<UserProfile | null>(null);
  const [pinFor, setPinFor] = useState<UserProfile | null>(null);
  const [pin, setPin] = useState("");

  const refresh = useCallback(async () => {
    try {
      setData(await getUsers());
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await action();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const switchTo = (profile: UserProfile) => {
    // A PIN is only asked for when there is one; a household of one should
    // never be interrogated by its own matrix.
    if (profile.hasPin) {
      setPin("");
      setPinFor(profile);
      return;
    }
    run(() => signInUser(profile.id));
  };

  if (!data) return null;

  return (
    <SettingsSection
      title="Users"
      icon={<PeopleRoundedIcon fontSize="small" color="primary" />}
      action={<Chip size="small" variant="outlined" label={`${data.profiles.length}`} />}
    >
      {error ? <Alert severity="error" onClose={() => setError("")}>{error}</Alert> : null}
      {data.signInRequired ? (
        <Alert severity="info">Nobody is signed in. Pick who is using this matrix.</Alert>
      ) : null}

      <Stack spacing={1}>
        {data.profiles.map((profile) => {
          const active = profile.id === data.activeId;
          return (
            <Box
              key={profile.id}
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 1.5,
                p: 1.25,
                border: "1px solid",
                borderColor: active ? "primary.main" : "divider",
                borderRadius: `${RADIUS}px`,
                bgcolor: active ? "action.selected" : "transparent",
              }}
            >
              <Avatar profile={profile} size={44} />

              <Box sx={{ minWidth: 0, flex: 1 }}>
                <Stack direction="row" spacing={0.75} alignItems="center">
                  <Typography variant="body2" noWrap sx={{ fontWeight: 600 }}>
                    {profile.name}
                  </Typography>
                  {active ? <Chip size="small" color="primary" label="Using" sx={{ height: 18 }} /> : null}
                  {profile.hasPin ? <Chip size="small" variant="outlined" label="PIN" sx={{ height: 18 }} /> : null}
                </Stack>
                <Typography variant="caption" color="text.secondary">
                  Scores and controller layouts are theirs
                </Typography>
              </Box>

              <IconButton size="small" onClick={() => setDrawing(profile)} title="Draw a face">
                <BrushRoundedIcon fontSize="small" />
              </IconButton>
              {active ? null : (
                <Button size="small" variant="outlined" disabled={busy} onClick={() => switchTo(profile)}>
                  Switch
                </Button>
              )}
              {data.profiles.length > 1 ? (
                <IconButton size="small" color="error" onClick={() => setRemoving(profile)} title="Remove">
                  <DeleteOutlineRoundedIcon fontSize="small" />
                </IconButton>
              ) : null}
            </Box>
          );
        })}
      </Stack>

      <Stack direction="row" spacing={1} alignItems="flex-end">
        <Box sx={{ flex: 1 }}>
          <Field label="Add someone">
            <TextField
              value={name}
              placeholder="Name"
              onChange={(event) => setName(event.target.value)}
              inputProps={{ maxLength: 24 }}
            />
          </Field>
        </Box>
        <Button
          variant="contained"
          disabled={busy || !name.trim()}
          onClick={() => run(async () => { await createUser(name.trim()); setName(""); })}
        >
          Add
        </Button>
      </Stack>

      {drawing ? (
        <AvatarEditor
          profile={drawing}
          open
          onClose={() => setDrawing(null)}
          onSave={(avatar, palette) =>
            run(async () => {
              await updateUser(drawing.id, { avatar, palette });
              setDrawing(null);
            })
          }
        />
      ) : null}

      <Dialog open={pinFor !== null} onClose={() => setPinFor(null)} maxWidth="xs" fullWidth>
        <DialogTitle>{pinFor?.name}'s PIN</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            value={pin}
            onChange={(event) => setPin(event.target.value.replace(/\D/g, "").slice(0, 4))}
            inputProps={{ inputMode: "numeric", style: { letterSpacing: 8, fontSize: 24, textAlign: "center" } }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPinFor(null)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={pin.length !== 4}
            onClick={() =>
              run(async () => {
                await signInUser(pinFor!.id, pin);
                setPinFor(null);
              })
            }
          >
            Sign in
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={removing !== null} onClose={() => setRemoving(null)}>
        <DialogTitle>Remove {removing?.name}?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Their high scores and controller layouts go with them. Anything installed
            stays, because apps belong to the matrix rather than to one person.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRemoving(null)}>Keep</Button>
          <Button
            color="error"
            variant="contained"
            onClick={() => run(async () => { await deleteUser(removing!.id); setRemoving(null); })}
          >
            Remove
          </Button>
        </DialogActions>
      </Dialog>
    </SettingsSection>
  );
}
