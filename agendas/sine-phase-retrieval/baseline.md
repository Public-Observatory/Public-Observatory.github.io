# A polynomial-density baseline

The old question asked whether a stable sine spectrum can grow faster than logarithmically. The following deduction from [Christ, Pineau and Taylor, Proposition 4](https://arxiv.org/html/2205.00187v2) answers that weaker question affirmatively. The construction and the checks below are included so the revised density target has a verifiable starting point.

Call $A\subseteq\{1,2,\ldots\}$ a $B_3$ set if equality of two sums of three elements, with repetition allowed, forces equality of the two multisets. Put $\Lambda:=\{3a+1:a\in A\}$. Then $E_\Lambda$ does stable phase retrieval.

**Why the criterion applies.** The affine change preserves the $B_3$ property. It also implies the $B_2$ property: append the same element to an equality of two-term sums. Consequently positive differences of distinct elements of $\Lambda$ have unique representations, and unordered two-term sums, including doubles, have unique representations. Sums are $2$ modulo $3$, whereas differences are $0$ modulo $3$, so a positive difference cannot equal a sum.

Write $r_n:=\sqrt2\sin(2\pi nx)$ and $s_n:=r_n^2-1$. The formulas

$$s_n=-\cos(4\pi nx),\qquad r_mr_n=\cos(2\pi(m-n)x)-\cos(2\pi(m+n)x)$$

therefore show that $\{1,s_n,r_mr_n:m<n\}$ is orthogonal. Moreover, $\|r_n\|_4^4=3/2$ and $\|r_mr_n\|_2^2=1$ for $m\ne n$.

For a finitely supported coefficient sequence $c$, set $P(x):=\sum_{n\in\Lambda}c_ne^{2\pi inx}$. Expanding $\int|P|^6$ and using the $B_3$ property gives

$$\|P\|_6^6\leq 6\Bigl(\sum_n|c_n|^2\Bigr)^3.$$

Indeed each ordered triple has at most six permutations with the same sum. For real $c_n$, the corresponding sine polynomial is $\sqrt2\operatorname{Im}P$, so

$$\Bigl\|\sum_n c_nr_n\Bigr\|_6\leq\sqrt2\,6^{1/6}\Bigl(\sum_n c_n^2\Bigr)^{1/2}.$$

This extends to the closed span by completion. All the hypotheses of Proposition 4, with $q=6$, now hold.

**Obtaining density.** Choose $A$ greedily, always adjoining the least larger integer preserving the $B_3$ property. If $j$ elements have been chosen, a forbidden next integer $x$ satisfies, after canceling common occurrences of $x$, an equation

$$kx=\sum_{i=1}^{r}a_i-\sum_{i=1}^{s}b_i,\qquad 1\leq k\leq3,\quad r+s\leq5,$$

with all $a_i,b_i$ among the chosen elements. There are at most a constant times $j^5$ such equations, each determining at most one $x$. Every previously rejected integer remains forbidden as the set grows. Thus the $j$th chosen element is at most a constant times $j^5$. It follows that $|A\cap[1,N]|\geq cN^{1/5}$ for all sufficiently large $N$. The affine change to $\Lambda$ preserves this exponent.

This is a baseline, not a best-density claim. Its role is to remove a question already settled by a short application of an available criterion.
