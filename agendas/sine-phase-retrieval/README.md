# Stable phase retrieval for sine series

Which arithmetic restrictions on a sine spectrum prevent two signals from having almost the same modulus?

For an infinite set $\Lambda\subseteq\{1,2,\ldots\}$, put

$$E_\Lambda:=\overline{\operatorname{span}_{\mathbb R}\{\sqrt2\sin(2\pi n x):n\in\Lambda\}}^{\,L^2[0,1]}.$$

Write $C(\Lambda)$ for the least constant in

$$\min\{\|f-g\|_2,\|f+g\|_2\}\leq C(\Lambda)\,\||f|-|g|\|_2\qquad(f,g\in E_\Lambda),$$

and set $C(\Lambda):=\infty$ if no finite constant exists. Stability means $C(\Lambda)<\infty$.

There is a useful way to see the obstruction. For real $u,v$, the pointwise identity

$$\bigl||u+v|-|u-v|\bigr|=2\min\{|u|,|v|\}$$

shows that stability is equivalent to a uniform lower bound on $\|\min\{|u|,|v|\}\|_2$ over unit vectors $u,v\in E_\Lambda$. Indeed, substitute $f=u+v$, $g=u-v$; independent normalization of $u,v$ gives the converse. The question is whether two unit sine series can concentrate on nearly disjoint sets.

[Christ, Pineau and Taylor, Example 3 and Proposition 4](https://arxiv.org/html/2205.00187v2), establish stability for $\Lambda=\{4^k:k\geq1\}$ using orthogonality of products and a higher-integrability estimate. Their argument does not directly cover the powers of two. The questions below concern how far the phenomenon extends.

## 1. Does lacunarity alone give uniform stability?

For each $q>1$, is there $C_q<\infty$ such that

$$C(\{n_k:k\geq1\})\leq C_q\qquad\text{whenever }n_{k+1}\geq qn_k?$$

**First target:** settle $\Lambda=\{2^k:k\geq1\}$. The relation $2^{k+2}-2^{k+1}=2\cdot2^k$ creates a collision between product frequencies, so the orthogonality proof for powers of four does not apply. Does it merely complicate that proof, or permit almost disjoint unit vectors?

A positive answer would make gap size, rather than exact additive separation, sufficient. A negative answer should distinguish a single unstable infinite spectrum from a sequence of stable spectra whose constants diverge at the same fixed $q$. These refute different assertions. The exact value of $C(\{4^k\})$ is secondary to this distinction.

## 2. How dense can a stable sine spectrum be?

For an infinite $\Lambda$, define

$$a_\Lambda(N):=|\Lambda\cap[1,N]|,\qquad \alpha_*:=\sup_{C(\Lambda)<\infty}\limsup_{N\to\infty}\frac{\log a_\Lambda(N)}{\log N}.$$

**Is $\alpha_*>1/3$?** Equivalently, can one construct one infinite stable spectrum and constants $c,\varepsilon>0$ with $a_\Lambda(N)\geq cN^{1/3+\varepsilon}$ for arbitrarily large $N$?

The [baseline construction](baseline.md) already gives $a_\Lambda(N)\geq cN^{1/5}$ for every sufficiently large $N$. Thus merely exceeding logarithmic growth is not the target. One third is a meaningful next threshold: sets with unique three-term sums have at most order $N^{1/3}$ elements in $[1,N]$, by counting their three-term sums. Beating it would leave that construction behind. It is not asserted to be a barrier for stability itself.

A density obstruction valid for every stable sine spectrum would also be substantial progress. Finite sets with increasing cardinality count only if their stability constants stay bounded; such sets need not assemble into one infinite example.

## 3. Does stability force higher integrability?

If $C(\Lambda)<\infty$, must there be $p>2$ and $K<\infty$ such that

$$\|f\|_p\leq K\|f\|_2\qquad(f\in E_\Lambda)?$$

This asks whether a familiar ingredient of the sufficient conditions is actually necessary. A positive answer would connect nonlinear recovery to the theory of $\Lambda(p)$ sets; a negative answer would exhibit stability beyond all these norm comparisons.

There is an elementary necessary condition. Fix $n\in\Lambda$ and put $v:=\sqrt2\sin(2\pi nx)$. For every unit vector $u\in E_\Lambda$, the overlap criterion gives

$$C(\Lambda)^{-2}\leq\int_0^1\min\{|u|^2,|v|^2\}\,dx\leq\sqrt2\|u\|_1.$$

Hence stability forces equivalence of the $L^1$ and $L^2$ norms on this space. The research question is whether the arithmetic structure forces an improvement above $2$. A counterexample must use one infinite spectrum with finite $C(\Lambda)$ and no such bound for any $p>2$.

## Contributions

Prove a stated case, produce a counterexample, or establish a necessary condition that separates the three questions. For instability, exhibit unit vectors whose overlap tends to zero. Numerical searches should report the frequencies, coefficients, quadrature error, and normalization; a small sampled overlap alone does not prove instability. The baseline is a deduction supplied with this revision, not a claim of a new theorem or an independently reviewed result.
