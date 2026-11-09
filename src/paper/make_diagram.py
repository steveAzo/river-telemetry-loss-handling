"""System model figure for Section 3 of the Paper 2 draft, drawn in the plain style of the journal literature
(monochrome, square boxes, thin lines, serif labels, dimension-style brackets).
Writes draft/figs/fig_system.pdf and .png (run from Paper2/: python -I src/paper/make_diagram.py)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch

plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Times New Roman", "DejaVu Serif"]
plt.rcParams["pdf.fonttype"] = 42

LW = 0.8
FS = 7.2
DASH = (0, (3, 2))

fig, ax = plt.subplots(figsize=(7.2, 2.6))
ax.set_xlim(0, 160)
ax.set_ylim(0, 52)
ax.axis("off")


def box(x, y, w, h, text, fs=FS, fc="white"):
    ax.add_patch(Rectangle((x, y), w, h, fc=fc, ec="black", lw=LW))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, linespacing=1.2)


def arrow(p, q, ls="-"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=7, color="black", lw=LW, linestyle=ls,
                                 shrinkA=0, shrinkB=0))


def line(xs, ys, ls="-"):
    ax.plot(xs, ys, color="black", lw=LW, ls=ls, solid_capstyle="butt")


def text(x, y, s, ha="center", fs=6.6):
    ax.text(x, y, s, ha=ha, va="center", fontsize=fs, linespacing=1.2)


# ---- sensor node: dashed outline around its parts
ax.add_patch(Rectangle((1, 2), 74, 44, fc="none", ec="black", lw=LW, ls=(0, (4, 2))))
text(38, 49, "Sensor node", fs=FS)

box(3, 20, 20, 12, "Sensors\n(T, EC, DO, pH)", fs=6.8)
box(28, 20, 18, 12, "Buffer\n(kept until\nconfirmed)")
box(52, 20, 21, 12, "Upload logic:\nhourly batch,\nalarm, back-off")
box(52, 37, 21, 7, "Event detector")
box(51, 5, 23, 10, "Server's picture,\nas the node sees it", fs=6.6)

arrow((23, 26), (28, 26))                      # sensors -> buffer
arrow((46, 26), (52, 26))                      # buffer -> upload logic
line([13, 13], [32, 40.5])                     # sensors -> event detector
line([13, 51.5], [40.5, 40.5])
arrow((51.5, 40.5), (52, 40.5))
arrow((62.5, 37), (62.5, 32))                  # alarm -> upload logic
arrow((62.5, 15), (62.5, 20))                  # server picture -> upload logic (bounded-error trigger)
text(66.5, 34.5, "alarm", ha="left", fs=5.8)
text(66.5, 17.6, "trigger", ha="left", fs=5.8)

# ---- path to the server
xs = [82, 103, 123, 144]
ws = [16, 15, 17, 15]
names = ["Radio link\n(LoRaWAN\nor NB-IoT)", "Gateway\nor cell", "Backhaul,\nnetwork\nserver", "Application\nserver"]
for x, w, t in zip(xs, ws, names):
    box(x, 20, w, 12, t, fc="#e9e9e9" if t.startswith("Application") else "white")

arrow((73, 29), (82, 29))                      # node -> radio link (uplink)
arrow((82, 23), (73, 23), ls=DASH)             # acknowledgement back to the node
for x0, w0, x1 in [(82, 16, 103), (103, 15, 123), (123, 17, 144)]:
    arrow((x0 + w0, 29), (x1, 29))
    arrow((x1, 23), (x0 + w0, 23), ls=DASH)

# ---- dimension-style brackets
def bracket(x0, x1, y, s, ty):
    line([x0, x1], [y, y])
    line([x0, x0], [y - 1.1, y + 1.1])
    line([x1, x1], [y - 1.1, y + 1.1])
    text((x0 + x1) / 2, ty, s)


bracket(82, 98, 16, "radio losses:\nshort bursts", 10.5)
bracket(103, 159, 16, "system outage: gateway, backhaul, or\nserver down for every node (hours to days)", 10.5)
bracket(82, 159, 37, "delivery gap: a run of slots in which no reading reaches the server", 41)
text(82, 3.2, "Solid arrows: data.  Dashed arrows: acknowledgements, from the network server (LoRaWAN) or the application (NB-IoT).",
     ha="left", fs=6.0)

fig.savefig("draft/figs/fig_system.pdf", bbox_inches="tight")
fig.savefig("draft/figs/fig_system.png", dpi=220, bbox_inches="tight")
print("fig_system written")
