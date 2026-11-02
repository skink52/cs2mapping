/* Recovers GoldSrc player-clip volumes from a BSP's collision hulls.
 *
 * Clip brushes only exist in the collision hulls (1-3), not in the visible hull 0. A point counts as clip when the
 * crouched-player hull (3) says "solid" for every player origin around it (erosion by the hull box: this undoes the
 * hull expansion and gives back the brush volume) while hull 0 has no solid within 16 units of it.
 * Components smaller than a 32-unit cube are dropped (they are the inside corners the hull expansion rounds off).
 *
 * usage: cliphull <map.bsp> <grid> <out.txt>      writes one box per line: x0 y0 z0 x1 y1 z1 (world units)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

typedef struct { float n[3]; float d; int type; } plane_t;
typedef struct { uint32_t plane; int16_t children[2]; int16_t mins[3], maxs[3]; uint16_t firstface, numfaces; } node_t;
typedef struct { int32_t plane; int16_t children[2]; } clipnode_t;
typedef struct { int32_t contents; int32_t visofs; int16_t mins[3], maxs[3]; uint16_t fm, nm; uint8_t amb[4]; } leaf_t;
typedef struct { float mins[3], maxs[3], origin[3]; int32_t headnode[4]; int32_t visleafs, firstface, numfaces; } model_t;

static plane_t *planes; static node_t *nodes; static clipnode_t *clipnodes; static leaf_t *leaves; static model_t *models;

static int contents0(const double p[3]) {
    int n = models[0].headnode[0];
    while (n >= 0) {
        const node_t *nd = &nodes[n]; const plane_t *pl = &planes[nd->plane];
        double d = p[0] * pl->n[0] + p[1] * pl->n[1] + p[2] * pl->n[2] - pl->d;
        n = nd->children[d >= 0 ? 0 : 1];
    }
    return leaves[-n - 1].contents;
}
static int contentsh(int hull, const double p[3]) {
    int n = models[0].headnode[hull];
    while (n >= 0) {
        const clipnode_t *nd = &clipnodes[n]; const plane_t *pl = &planes[nd->plane];
        double d = p[0] * pl->n[0] + p[1] * pl->n[1] + p[2] * pl->n[2] - pl->d;
        n = nd->children[d >= 0 ? 0 : 1];
    }
    return n;
}

static int NX, NY, NZ;
#define IDX(x, y, z) (((size_t)(z) * NY + (y)) * NX + (x))

/* binary erosion (want=1) / dilation (want=0) along one axis with half-width r, in place, via run counting */
static void pass(uint8_t *a, int axis, int r, int erode) {
    int len = axis == 0 ? NX : axis == 1 ? NY : NZ;
    int o1 = axis == 0 ? NY : NX, o2 = axis == 2 ? NY : NZ;
    uint8_t *line = malloc(len), *out = malloc(len);
    int *pre = malloc(sizeof(int) * (len + 1));
    for (int j = 0; j < o2; j++) for (int i = 0; i < o1; i++) {
        for (int k = 0; k < len; k++) {
            size_t id = axis == 0 ? IDX(k, i, j) : axis == 1 ? IDX(i, k, j) : IDX(i, j, k);
            line[k] = a[id];
        }
        pre[0] = 0;
        for (int k = 0; k < len; k++) pre[k + 1] = pre[k] + line[k];
        for (int k = 0; k < len; k++) {
            int lo = k - r, hi = k + r;
            int clo = lo < 0 ? 0 : lo, chi = hi >= len ? len - 1 : hi;
            int ones = pre[chi + 1] - pre[clo];
            if (erode) {           /* outside the grid counts as solid */
                int outside = (clo - lo) + (hi - chi);
                out[k] = (ones + outside) == (2 * r + 1);
            } else out[k] = ones > 0;
        }
        for (int k = 0; k < len; k++) {
            size_t id = axis == 0 ? IDX(k, i, j) : axis == 1 ? IDX(i, k, j) : IDX(i, j, k);
            a[id] = out[k];
        }
    }
    free(line); free(out); free(pre);
}

static size_t *stack; static size_t stack_cap;
static void push(size_t v, size_t *sp) { if (*sp >= stack_cap) { stack_cap *= 2; stack = realloc(stack, stack_cap * sizeof(size_t)); } stack[(*sp)++] = v; }

/* flood fill component of value `from` starting at s, setting it to `to`; returns size */
static size_t flood(uint8_t *a, size_t s, uint8_t from, uint8_t to) {
    size_t sp = 0, count = 0;
    a[s] = to; push(s, &sp);
    while (sp) {
        size_t v = stack[--sp]; count++;
        int x = v % NX, y = (v / NX) % NY, z = v / ((size_t)NX * NY);
        int nb[6][3] = {{x - 1, y, z}, {x + 1, y, z}, {x, y - 1, z}, {x, y + 1, z}, {x, y, z - 1}, {x, y, z + 1}};
        for (int k = 0; k < 6; k++) {
            int X = nb[k][0], Y = nb[k][1], Z = nb[k][2];
            if (X < 0 || Y < 0 || Z < 0 || X >= NX || Y >= NY || Z >= NZ) continue;
            size_t w = IDX(X, Y, Z);
            if (a[w] == from) { a[w] = to; push(w, &sp); }
        }
    }
    return count;
}

int main(int argc, char **argv) {
    if (argc < 4) { fprintf(stderr, "usage: cliphull map.bsp grid out.txt\n"); return 1; }
    FILE *f = fopen(argv[1], "rb"); if (!f) { perror(argv[1]); return 1; }
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
    uint8_t *d = malloc(sz); fread(d, 1, sz, f); fclose(f);
    int32_t *hdr = (int32_t *)d;
    #define LUMP(i) (d + hdr[1 + 2 * (i)])
    planes = (plane_t *)LUMP(1); nodes = (node_t *)LUMP(5); clipnodes = (clipnode_t *)LUMP(9); leaves = (leaf_t *)LUMP(10); models = (model_t *)LUMP(14);
    double g = atof(argv[2]);
    double lo[3], hi[3];
    for (int k = 0; k < 3; k++) { lo[k] = models[0].mins[k] - 64; hi[k] = models[0].maxs[k] + 64; }
    NX = (int)((hi[0] - lo[0]) / g) + 1; NY = (int)((hi[1] - lo[1]) / g) + 1; NZ = (int)((hi[2] - lo[2]) / g) + 1;
    size_t N = (size_t)NX * NY * NZ;
    fprintf(stderr, "grid %d x %d x %d = %zu\n", NX, NY, NZ, N);
    uint8_t *s3 = malloc(N), *s0 = malloc(N);
    for (int z = 0; z < NZ; z++) for (int y = 0; y < NY; y++) for (int x = 0; x < NX; x++) {
        double p[3] = {lo[0] + x * g, lo[1] + y * g, lo[2] + z * g};
        size_t i = IDX(x, y, z);
        s3[i] = contentsh(3, p) == -2;
        int c0 = contents0(p);
        s0[i] = (c0 == -2 || c0 == -6);
    }
    int rxy = (int)(16 / g + 0.001), rz = (int)(18 / g + 0.001), rn = (int)(16 / g + 0.001);
    pass(s3, 0, rxy, 1); pass(s3, 1, rxy, 1); pass(s3, 2, rz, 1);
    pass(s0, 0, rn, 0); pass(s0, 1, rn, 0); pass(s0, 2, rn, 0);
    size_t total = 0;
    for (size_t i = 0; i < N; i++) { s3[i] = s3[i] && !s0[i]; total += s3[i]; }
    free(s0);
    fprintf(stderr, "clip voxels before filtering: %zu\n", total);
    stack_cap = 1 << 20; stack = malloc(stack_cap * sizeof(size_t));
    size_t minvox = (size_t)((32.0 / g) * (32.0 / g) * (32.0 / g));
    int kept = 0, dropped = 0;
    for (size_t i = 0; i < N; i++) if (s3[i] == 1) {
        size_t n = flood(s3, i, 1, 2);
        if (n < minvox) { flood(s3, i, 2, 0); dropped++; }
        else { flood(s3, i, 2, 3); kept++; }
    }
    fprintf(stderr, "components kept %d dropped %d\n", kept, dropped);
    /* greedy boxes over value 3 */
    FILE *o = fopen(argv[3], "w"); int boxes = 0;
    for (int z = 0; z < NZ; z++) for (int y = 0; y < NY; y++) for (int x = 0; x < NX; x++) {
        if (s3[IDX(x, y, z)] != 3) continue;
        int x1 = x; while (x1 + 1 < NX && s3[IDX(x1 + 1, y, z)] == 3) x1++;
        int y1 = y;
        for (;;) {
            if (y1 + 1 >= NY) break;
            int ok = 1; for (int xx = x; xx <= x1; xx++) if (s3[IDX(xx, y1 + 1, z)] != 3) { ok = 0; break; }
            if (!ok) break; y1++;
        }
        int z1 = z;
        for (;;) {
            if (z1 + 1 >= NZ) break;
            int ok = 1;
            for (int yy = y; yy <= y1 && ok; yy++) for (int xx = x; xx <= x1; xx++) if (s3[IDX(xx, yy, z1 + 1)] != 3) { ok = 0; break; }
            if (!ok) break; z1++;
        }
        for (int zz = z; zz <= z1; zz++) for (int yy = y; yy <= y1; yy++) for (int xx = x; xx <= x1; xx++) s3[IDX(xx, yy, zz)] = 4;
        /* a sample stands for the cell centred on it */
        fprintf(o, "%g %g %g %g %g %g\n", lo[0] + (x - 0.5) * g, lo[1] + (y - 0.5) * g, lo[2] + (z - 0.5) * g,
                lo[0] + (x1 + 0.5) * g, lo[1] + (y1 + 0.5) * g, lo[2] + (z1 + 0.5) * g);
        boxes++;
    }
    fclose(o);
    fprintf(stderr, "boxes %d\n", boxes);
    return 0;
}
