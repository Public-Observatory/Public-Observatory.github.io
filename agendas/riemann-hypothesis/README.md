# Estimates towards the Riemann hypothesis

This agenda asks for two analytic advances: an extension of the moment estimate used in a proposed fixed zero-free region, and a weaker route to improving the proportion of simple zeros on the critical line. Each has a concrete intermediate target. Neither asks contributors simply to solve RH or to recheck an entire paper.

Let $\zeta$ denote the meromorphic continuation of $\zeta(s):=\sum_{n\geq1}n^{-s}$, initially defined for $\operatorname{Re}s>1$. RH says that every zero in $0<\operatorname{Re}s<1$ lies on $\operatorname{Re}s=1/2$. A fixed zero-free half-plane excludes zeros at every height; a proportion estimate allows exceptions. The two questions therefore measure different kinds of progress.

## 1. Can the marked fourth moment reach below seven eighths?

**Does the estimate in Lemma 18.1 of the [September 2026 preprint](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/preprints/The-Quasi-Riemann-Hypothesis-September-30-2026/paper.pdf) extend to some interval $\kappa_0\leq\kappa\leq1$ with $\kappa_0<3/4$, and can that extension yield a zero-free half-plane $\operatorname{Re}s>\theta$ with $\theta<7/8$?**

Use that pinned version's definitions of the row characters, masks, smooth polynomials, and prime factors. For positive total prime length $z$, its stated admissibility condition is

$$n_1+n_2+6\kappa z\leq M,$$

under the additional hypothesis $\beta^*\leq(1+\kappa)/2$ when $\kappa<1$; here $\beta^*$ is the supremum of the real parts of nontrivial zeros in the preprint's primitive finite-order Hecke family over $\mathbb Q(\sqrt{-3})$. The theorem is stated for $3/4\leq\kappa\leq1$. Its use of $\kappa=2\beta^*-1$ explains why extending this range is a concrete target for moving below $7/8$.

The first milestone is to identify whether $3/4$ is essential to the moment argument. Prove an extension, or isolate the exact estimate that prevents one. A counterexample must obey the row, coefficient, and mask hypotheses. An extension alone does not imply a new zero-free region: the continuation argument, prime supply, row counts, and contour ranges must also be established at the new boundary.

This is conditional research until the required inputs have been checked. The existing [first-stage verification](https://github.com/Public-Observatory/riemann-hypothesis/issues/1) and [parameter checks](https://github.com/Public-Observatory/riemann-hypothesis/issues/4) remain supporting tasks; neither is recorded here as completed. A numerical optimum using the old hypotheses outside their stated ranges is not progress on this question.

## 2. Can one-sided higher-moment estimates establish 68%?

Let $N(T,2T)$ count nontrivial zeros with $T<\operatorname{Im}\rho\leq2T$, with multiplicity, and let $N_0^{\mathrm s}(T,2T)$ count the simple zeros in that range on the critical line. **Can one prove**

$$\liminf_{T\to\infty}\frac{N_0^{\mathrm s}(T,2T)}{N(T,2T)}\geq0.68$$

**using inequalities for the third and fourth trace moments of finite restrictions of Weil's form, rather than full higher-moment asymptotics?**

Use the matrix $\widetilde G_T$ and normalization in [the August 2026 paper](https://www-cdn.anthropic.com/95c246936988e43127bc6b2ceb7077c1dad2d68e.pdf). Its reported bound is $0.67250\ldots$. Section 7.2 already discusses stronger conclusions conditional on higher moments. Merely recovering those conditional conclusions would not answer this question.

A useful first result would specify explicit inequalities on $d_T^{-1}\operatorname{tr}(\widetilde G_T^j)$, $j=3,4$, where $d_T$ is the matrix dimension, sufficient for the target when combined with the stated first two moments and zero-block information. Prove the implication with a positive allowance for errors. Then identify the weighted prime-correlation estimate needed for those inequalities. The point is to find a weaker analytic target than evaluating every higher moment asymptotically; the full question requires proving that target unconditionally.

An obstruction is valuable too: exhibit an admissible family of Hermitian matrices and zero blocks showing that a specified proposed set of moment inequalities cannot suffice. Positive eigenvalues alone do not count simple zeros, and a proportion of one would still allow a sparse set of off-line zeros.

## Supporting work and evidence

Keep [reconstruction of the proportion argument](https://github.com/Public-Observatory/riemann-hypothesis/issues/8) as supporting work for Question 2. Distinguish checked statements from analytic inputs assumed from the papers. For either question, a contribution should state a theorem or counterexample, all parameter ranges, and which existing inputs it uses. Exact or interval computations can certify a finite inequality; they cannot supply an unproved asymptotic estimate.

The two recent papers motivate these targets. This revision does not certify their proofs or claim independent verification of their principal results.
