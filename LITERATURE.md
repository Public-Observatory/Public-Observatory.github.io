# Applied mathematics research agendas: a literature map

Reviewed 10 October 2026. Working notes for drafting research agendas for the [Public Observatory](https://public-observatory.github.io/), following the aims in [VISION.md](VISION.md).

The strongest recurring question is how to reduce the cost of scientific inference and prediction while retaining guarantees that matter for the intended use. This connects numerical analysis to approximation theory, probability, information theory, algorithms, and control. The ten directions below are a synthesis of prominent themes in the selected literature, not a ranking of all applied mathematics. The sources favour computational mathematics, US research programmes, and European industrial mathematics; mathematical biology, optimisation outside simulation, and other substantial areas would need separate reviews.

The community reports were examined principally through their research-priority sections. Surveys and selected subsequent papers supply mathematical context and existing baselines. **The proposed Observatory questions are our formulations, not open problems certified by the reports.** Before publishing an agenda, check its exact formulation against the current literature. A priority identified in 2008 or 2014 is evidence of motivation, not evidence that a question remains unanswered in 2026.

## Core white papers and community reports

These are the original eight reports, supplemented by the randomized-algorithms report for its particularly direct connection to theoretical computer science (TCS). The table distinguishes broad strategy from concrete research programmes.

| ID | Source and type | What to read and why |
| --- | --- | --- |
| W1 | National Research Council, [*The Mathematical Sciences in 2025*][W1] (2013). Consensus strategy report. | Chapters 2–4: uncertainty quantification, inverse problems, computation, data, and connections across disciplines. Useful for the overall case for applied mathematics; less suitable as a source of sharply stated open problems. The title names its planning horizon, not its publication year. |
| W2 | DOE community panel, [*Applied Mathematics at the U.S. Department of Energy: Past, Present and a View to the Future*][W2] (2008). Programme strategy report. | Chapter 2: multiscale and multiphysics models, stochastic effects, data–model fusion, sensitivity, uncertainty, optimisation, and inversion. A useful organising principle is to work backwards from what a scientific question requires. |
| W3 | DOE, [*Applied Mathematics Research for Exascale Computing*][W3] (2014). Community research roadmap. | §§4.2–4.6: analysis, discretisation, coupling, parallel time integration, solvers, data reduction, and correctness. Especially §4.4.3 on communication, synchronisation, compression, and precision. The durable mathematical issue is the cost model under which an algorithm is efficient. |
| W4 | National Research Council, [*Assessing the Reliability of Complex Models: Mathematical and Statistical Foundations of Verification, Validation, and Uncertainty Quantification*][W4] (2012). Consensus research report. | Chapters 4–5 and §7.3: reduced models, model discrepancy, extrapolation, rare events, and error estimation for specified outputs. Keep verification of a numerical solution separate from validation of its physical model. |
| W5 | Rüde, Willcox, McInnes and colleagues, [*Research and Education in Computational Science and Engineering*][W5] (2018; preprint 2016). SIAM community position report. | §2: algorithms, parallelism, data, software, and predictive science. Connects solving a forward problem to the repeated solves required by inference, optimisation, and control. |
| W6 | DOE, [*Basic Research Needs for Scientific Machine Learning: Core Technologies for Artificial Intelligence*][W6] (2019; workshop 2018). Research-priority report. | Chapter 2: domain awareness, interpretability, robustness, data-intensive learning, enhanced simulation, and decision support. §§2.3, 2.5, and 2.6 are especially useful for reliability, algorithm selection, and adaptive acquisition of data. |
| W7 | EU-MATHS-IN, [*Modelling, Simulation and Optimisation in Data-rich Environment: Strategic Research Agenda*][W7] (2020). European industrial-mathematics roadmap. | §6, especially model reduction, optimisation, systems and control, inverse problems, uncertainty, and digital twins. Makes the interaction among these subjects explicit, including constraints from online use and scarce data. |
| W8 | National Academies, [*Foundational Research Gaps and Future Directions for Digital Twins*][W8] (2024). Consensus research agenda. | Chapters 3 and 5–8: coupled models, data assimilation, decisions, and continuing validation as models change. Findings 3-6 and 3-7 concern component integration and multiphysics surrogates; Conclusion 3-2 requires accounting for training-data generation and training costs. |
| W9 | Buluç, Kolda, Wild and colleagues, [*Randomized Algorithms for Scientific Computing*][W9] (2021; revised arXiv version 2022). DOE workshop report. | §§3.2–3.6: sketching, discrete algorithms, streaming, complexity, and verification. Particularly useful for translating TCS guarantees into scientific workflows where randomised subroutines interact with numerical and statistical errors. |

## Ten prominent directions

### 1. Reliable error certificates for numerical and learned solvers

**Literature direction.** Develop computable error bounds for quantities of scientific interest, including nonlinear and coupled problems and learned approximations. The relevant starting points are [W4, §7.3.1][W4] and [W6, §2.3][W6]. Classical a posteriori estimation is a substantial existing theory; adding a neural network does not make certification a new problem.

**Mathematics and TCS.** Given an approximate solution $\widehat u$, seek a computable certificate $\eta(\widehat u)$ such that $|Q(u)-Q(\widehat u)|\leq\eta(\widehat u)$, where $u$ is the exact solution of the specified model and $Q$ is the requested output. How much cheaper can verification be than construction? A small residual controls error only through an appropriate stability estimate; estimating that stability can itself be expensive. Sampling a residual also introduces a separate statistical or quadrature problem.

**Candidate agenda.** Cheap, useful certificates for shock-containing solutions of one-dimensional scalar conservation laws. Separate entropy admissibility, shock displacement, residual evaluation, and interactions. Seek sharper bounds or cheaper verification with explicit assumptions; record counterexamples to plausible certificates. Cao, Li and Li's [2026 preprint on neural methods for scalar conservation laws](https://arxiv.org/abs/2604.27458) already gives rigorous error estimates and convergence rates. A proposed question must improve on or meaningfully extend an existing result. Numerical reference solutions can test sharpness but cannot establish a universal guarantee.

### 2. Algorithms that adapt precision and communication to the required accuracy

**Literature direction.** Redesign solvers around finite precision, memory traffic, and synchronisation, in addition to arithmetic work. Read [W3, §4.4.3][W3] and Higham and Mary's [*Mixed precision algorithms in numerical linear algebra*](https://doi.org/10.1017/S0962492922000022), *Acta Numerica* (2022), especially the discussion of iterative refinement and adaptive precision.

**Mathematics and TCS.** The natural questions involve bit complexity, conditioning, communication complexity, and the allocation of an error budget. An algorithm with fewer floating-point operations can move more data or require more global synchronisation. Conversely, reducing arithmetic precision can change convergence enough to erase its local savings. Complexity bounds should expose dependence on conditioning and the requested accuracy.

**Candidate agenda.** For elliptic equations with strongly varying coefficients on adaptive meshes, select arithmetic precision by region or multigrid level while bounding rounding and iteration errors relative to discretisation error. Compare costs at equal accuracy, including precision conversions and verification. [McCormick, Benzaken and Tamstorf (2020)](https://arxiv.org/abs/2007.06614) already analyse mixed-precision multigrid in the energy norm and introduce progressive precision. The proposed target is a practical adaptive rule with guarantees under coefficient contrast and refinement, not the existence of mixed-precision multigrid.

### 3. Randomised compression that remains valid inside an adaptive computation

**Literature direction.** Use sketches, random sampling, sparsification, and streaming summaries to avoid storing or repeatedly accessing full scientific datasets. [W9, §§3.2–3.6][W9] supplies the roadmap. Martinsson and Tropp's [*Randomized Numerical Linear Algebra: Foundations and Algorithms*](https://arxiv.org/abs/2002.01387), *Acta Numerica* (2020), supplies the mathematical background, including error estimation and single-pass algorithms.

**Mathematics and TCS.** A guarantee for a fixed input independent of a random sketch need not survive reuse when later inputs depend on earlier outputs. This is a concrete connection to adaptive data analysis and adversarial streaming. [Hardt and Woodruff, STOC 2013](https://arxiv.org/abs/1211.1056), establish limitations on linear sketches under adaptively chosen queries. Their setting is a warning about assumptions, not a theorem that every adaptive scientific solver fails.

**Candidate agenda.** Determine when a sketch can be reused across a sequence of linearised inverse problems or Krylov iterations. Compare fresh randomness, periodic refresh, and reuse with independent checks. State exactly how the iterates depend on the sketch, then prove an overall failure bound and quantify saved matrix accesses. Small constructed failures are valuable contributions alongside faster algorithms. A companion question is which downstream quantities a compressed representation must preserve: matrix error alone may not control a posterior or a decision.

### 4. The approximation, information, and computational complexity of operator learning

**Literature direction.** Learn solution maps across families of PDE inputs, with guarantees that explain when the approach is efficient. This develops the scientific-learning priorities of [W6][W6]. Useful foundations are DeVore, Hanin and Petrova's [*Neural Network Approximation*](https://arxiv.org/abs/2012.14501), *Acta Numerica* (2021), and Kovachki and colleagues' [*Neural Operator: Learning Maps Between Function Spaces With Applications to PDEs*](https://www.jmlr.org/papers/v24/21-1524.html), *JMLR* (2023).

**Mathematics and TCS.** Distinguish four questions: whether a small representation exists; how many observations identify it; whether it can be found efficiently; and whether its accuracy survives a change of discretisation or input distribution. Universal approximation answers none of the latter three by itself. Nonlinear widths, metric entropy, regularity, and oracle lower bounds offer ways to identify which assumptions make learning tractable. Specify whether access is to point samples, complete solution fields, or a simulator: these are different information models.

**Candidate agenda.** For a precisely defined family of elliptic coefficient fields, obtain upper and lower bounds for learning the solution operator at a fixed output tolerance. Compare smooth fields, high contrast, and changing geometry. Count the cost of generating training solutions and compare against conventional reduced models over a stated number of future queries. [W8, Conclusion 3-2][W8] provides the motivation for this full accounting.

### 5. Multiscale reduction, memory, and long-time dynamics

**Literature direction.** Derive affordable effective dynamics when the full system has unresolved variables or widely separated scales. Read [W2, §2.1.1][W2], [W7, §6.2][W7], and Givon, Kupferman and Stuart's [*Extracting macroscopic dynamics: model problems and algorithms*](https://authors.library.caltech.edu/records/s3yvm-6xj15), *Nonlinearity* (2004).

**Mathematics and TCS.** Removing variables generally introduces dependence on history and unresolved initial conditions. The interesting resource is the information retained in the reduced state: memory length, latent-state dimension, or a stochastic representation. This resembles a streaming question, but a streaming lower bound would require its own precise observation and prediction model. Approximation of individual trajectories, invariant statistics, and response to changed forcing are distinct goals; success at one does not establish the others.

**Candidate agenda.** How much memory is needed to reproduce selected long-time statistics and forcing responses in the two-scale Lorenz–96 system? Use a linear Gaussian model with explicitly computable memory as a baseline, then vary scale separation in the nonlinear model. Seek necessary conditions, truncation estimates, and reproducible failures of memoryless closures. [De Wit and colleagues (2026)](https://arxiv.org/abs/2507.16058) demonstrate learned Mori–Zwanzig models with accurate long-time statistics in a turbulence setting, so merely exhibiting a successful memory model is insufficient.

### 6. Identifiability and experimental design under imperfect models

**Literature direction.** Choose data that distinguish relevant explanations, accounting for noise and errors in the governing model. Read [W2, §§2.2.1 and 2.3.3][W2], [W7, §6.7][W7], and Huan, Jagalur and Marzouk's [*Optimal experimental design: Formulations and computations*](https://arxiv.org/abs/2407.16212), *Acta Numerica* (2024), especially §6.1 on misspecification.

**Mathematics and TCS.** The connections are to minimax estimation, active learning, information gain, and sequential decision-making. More informative measurements within the assumed model may still favour a wrong explanation. Distinguish parameter uncertainty from model discrepancy and identify what observations can separate them. If discrepancy is unrestricted, it can absorb parameter changes; useful results require a specified discrepancy class and observation budget.

**Candidate agenda.** Recover a diffusion coefficient from limited observations while allowing a constrained class of source-term errors. Characterise indistinguishable instances, derive recovery lower bounds, and design observations that reduce ambiguity. [Attia, Leyffer and Munson (2025)](https://doi.org/10.1137/24M1667543) already develop robust A-optimal design for linear Bayesian inverse problems with misspecified elements. The proposed extension concerns nonlinear recovery and structural error, with the source-error class fixed before optimisation.

### 7. Adaptive allocation of computation across model fidelities

**Literature direction.** Combine inexpensive approximations with occasional expensive solves in uncertainty propagation, inference, and optimisation. Read Peherstorfer, Willcox and Gunzburger's [*Survey of Multifidelity Methods in Uncertainty Propagation, Inference, and Optimization*](https://arxiv.org/abs/1806.10761), *SIAM Review* (2018), and Giles's [*Multilevel Monte Carlo methods*](https://doi.org/10.1017/S096249291500001X), *Acta Numerica* (2015). The broader motivation is repeated model evaluation in [W5, §2][W5].

**Mathematics and TCS.** This is resource allocation with correlated, differently biased information sources. The TCS connections include multi-armed bandits, best-arm identification, and algorithms using costly oracles. The analogy is incomplete unless it accounts for bias, cross-level coupling, and the fact that a surrogate may change during sampling. The target should be accuracy of the final expectation, posterior, or optimiser, rather than accuracy of every intermediate solve.

**Candidate agenda.** Allocate samples and mesh levels online for a random-coefficient elliptic PDE when costs and correlations are initially unknown. Seek a finite-budget guarantee relative to an allocation that knows those quantities, charging for pilot samples and model construction. Begin with established multilevel and control-variate allocations. The research question is what adaptation costs and when it preserves the promised error bound; combining two fidelities is already standard.

### 8. Rare events, tail accuracy, and reliable stopping

**Literature direction.** Estimate small probabilities when direct simulation is expensive and validation data may not contain the event. [W4, §§7.3.2–7.3.3][W4] explicitly identifies both rare-event computation and model discrepancy in the tails.

**Mathematics and TCS.** Average prediction error is a poor proxy for the accuracy of a threshold event. Relevant tools include large deviations, importance sampling, splitting, concentration inequalities, and sequential testing. For independent direct Bernoulli sampling, relative root-mean-square error $\varepsilon$ for an event of probability $p$ requires order $1/(p\varepsilon^2)$ samples when $p$ is small. Beating this baseline requires exploitable structure; it is not a general lower bound for all sampling or oracle models. Adaptive stopping requires a guarantee valid for the stopping procedure used.

**Candidate agenda.** Estimate a threshold probability for a diffusion PDE with random coefficients using adaptively refined surrogates. Separate sampling uncertainty, surrogate bias, and PDE discretisation error. Study finite-sample coverage and missed failure regions. [Cérou, Héas and Rousset's *Adaptive Reduced Multilevel Splitting*](https://arxiv.org/abs/2312.15256) already exploits certified surrogate errors. A useful extension would quantify guarantees and cost when both sampling and the surrogate evolve. Certifying a probability under an assumed input law does not validate that law physically.

### 9. Compositional guarantees for coupled models

**Literature direction.** Assemble complex simulations from components of different scales or fidelities while retaining conservation, stability, and useful error estimates. See [W3, §4.3.1][W3], [W8, Findings 3-6 and 3-7][W8], and van der Schaft and Jeltsema's [*Port-Hamiltonian Systems Theory: An Introductory Overview*](https://doi.org/10.1561/2600000002) (2014), a survey of an established framework for interconnected physical systems.

**Mathematics and TCS.** This connects small-gain and dissipativity arguments to compositional verification: what must each component promise about its inputs and outputs for a global guarantee to follow? As a simple baseline, if nonnegative component errors satisfy $e\leq b+Ge$, with $G\geq0$ and spectral radius below one, then $e\leq(I-G)^{-1}b$. The difficult work is obtaining informative interface bounds and extending them to nonlinear, time-dependent couplings. Local accuracy alone does not imply a useful global bound.

**Candidate agenda.** Couple reduced models of heat transfer across an interface. Establish which interface errors preserve energy balance and yield an output-error bound, then extend to nonlinear or learned components. Charge for the coupling and its verification. The initial heat problem is a baseline, not a claim of novelty. A promising target is updating one component while reusing valid guarantees for the rest of the system.

### 10. Decision and control guarantees with learned or approximate dynamics

**Literature direction.** Use models to choose actions and experiments, with guarantees on the resulting behaviour. Read [W6, §2.6][W6], [W7, §6.5][W7], [W8, Chapter 6][W8], and Brunke and colleagues' [*Safe Learning in Robotics: From Learning-Based Control to Safe Reinforcement Learning*](https://arxiv.org/abs/2108.06266), *Annual Review of Control, Robotics, and Autonomous Systems* (2022).

**Mathematics and TCS.** The central interaction is between system identification, exploration, robust control, and online regret. A model can predict typical observations well and still be unsuitable for optimisation, which actively seeks unusual inputs. Compare performance, constraint satisfaction, and computational cost separately. Mitzenmacher and Vassilvitskii's [*Algorithms with Predictions*](https://arxiv.org/abs/2006.09123) (2020 preprint) offers a useful design principle: benefit from accurate learned advice while retaining a stated fallback guarantee when it is wrong. Transferring this principle to numerical control requires new, explicitly stated assumptions.

**Candidate agenda.** For a controlled diffusion equation with uncertain coefficients, determine when a reduced model is sufficient to choose a control and when a full solve is necessary. Seek computable conditions for constraint satisfaction and an objective-gap bound; compare against full-model control and an established robust baseline. Begin with a convex, linear-quadratic problem. Nonlinear extension and adaptive model updates can follow once the certification and fallback costs are understood.

## Patterns and mathematical opportunities

The following are our interpretations of the source map and possible ways to organise future work.

**1. The unit of accuracy is moving towards the final task.** An accurate state vector, a calibrated posterior, a correct tail probability, and a good decision are different deliverables. The output-oriented viewpoint in W4 and the decision focus in W8 suggest asking which approximation errors actually affect the requested result. A TCS formulation can specify the output first and ask for the minimum information and computation needed to obtain it. This links directions 1, 3, 6, 7, 8, and 10.

**2. Approximation and verification should be designed together.** A heuristic or learned component may be useful if its output can be checked cheaply and corrected when necessary. The interesting theorem relates construction cost, verification cost, certificate sharpness, and fallback frequency. This is a proposed bridge between numerical error estimation and algorithms with predictions; it is not an assertion that classical proof-verification complexity transfers unchanged to continuous problems.

**3. Adaptivity changes the probability space.** Reusing sketches, choosing observations, updating surrogates, and stopping simulations all make future computation depend on past results. Guarantees for fixed inputs or a fixed sample size must be checked against that dependence. Hardt–Woodruff gives a concrete obstruction in one setting; the opportunity is to identify useful restricted settings, fresh-randomness schemes, or valid sequential checks. Directions 3, 6, 7, and 8 could share mathematical tools here.

**4. Reduced dimension is a hypothesis to explain.** Low rank, sparse dependence, smooth solution manifolds, short memory, and scale separation can make otherwise expensive problems tractable. Each is a mathematical assumption, not an automatic consequence of calling a method a surrogate. It is useful to pair an upper bound under such an assumption with a lower bound or counterexample when it fails. Direction 4 concerns representation and information; direction 5 adds dynamical memory and long-time behaviour.

**5. Complexity should include the work that an experiment hides.** Training data, parameter search, preconditioner setup, residual evaluation, data movement, and failed runs all consume resources. W3 foregrounds architecture costs; W8 explicitly includes surrogate training costs. A useful comparison fixes the same accuracy and reliability target, states the hardware or abstract access model, and reports both setup and repeated-use costs. Amortised gains depend on the number and distribution of future queries.

**6. Composition is a likely source of new mathematics.** Mature individual components do not automatically give a mature end-to-end method. A learned approximation inside an inverse problem, a sketch inside an adaptive solver, or a reduced model inside feedback changes the assumptions under which the component was analysed. Candidate work should identify the missing interface theorem. Direction 9 makes this issue explicit, while the other directions supply concrete instances.

**7. Numerical, statistical, and physical uncertainty must remain distinguishable.** Solving a chosen PDE accurately does not establish that it describes the experiment. A confidence statement for randomised computation does not account for omitted physics. The distinction in W4 is particularly important for directions 6 and 8: numerical guarantees can be precise even when physical validation remains conditional on modelling judgments.

## Which agendas to develop first

This is a judgment about fit to the Observatory, not a ranking of scientific importance.

| Candidate | Why it fits | First result worth seeking |
| --- | --- | --- |
| Adaptive precision, direction 2 | Mature baselines; manageable numerical experiments; clear accuracy and cost comparisons. | A certified precision-selection rule for a specified PDE family, or a counterexample delimiting an existing rule. |
| Adaptive sketch reuse, direction 3 | Direct TCS connection; meaningful lower bounds and small counterexamples; cheap independent checking. | A theorem giving conditions for safe reuse, together with a reproducible failure when those conditions are removed. |
| Memory in reduced dynamics, direction 5 | Connects analysis, dynamical systems, and computation; supports several independent contributions. | A memory–accuracy trade-off for a specified observable and regime, with uncertainty from finite trajectories reported. |
| PDE output certificates, direction 1 | Connects established numerical analysis with current scientific ML; certificates suit public checking. | A bound that is materially tighter or cheaper than a named baseline on a precisely defined problem class. |

Directions 6 and 9 are attractive for more theoretical agendas once their discrepancy classes and coupling assumptions are fixed. Directions 7, 8, and 10 need particular care in defining the sampling protocol and reference optimum. Direction 4 is a strong source of theorem questions, but a generic request to explain neural-operator efficiency would be too broad.

Before drafting an agenda, write down the model class, access to data or oracles, requested output, error metric, resource budget, and meaning of a guarantee. Identify a current theorem or algorithm that supplies the baseline. Then separate a genuine extension from a reproduction task and define what would count as a negative result. A few benchmark improvements alone do not establish the general mathematical claim.

## Reading routes for resuming this work

- **Broad orientation:** W1, W2, and W5; use W7 to connect the subjects to industrial requirements.
- **Numerical analysis and certification:** W3 §4.4.3, W4 §7.3, the Higham–Mary survey, then the current baseline in directions 1 or 2.
- **TCS and information limits:** W9 §§3.2–3.6, Martinsson–Tropp, Hardt–Woodruff, and *Algorithms with Predictions*. Then choose a concrete access model from directions 3, 4, or 7.
- **Inference and decisions:** W4 Chapter 5, W6 §2.6, Huan–Jagalur–Marzouk, and W8 Chapters 5–6. Distinguish recovery, experimental design, and control before choosing a question.
- **Dynamics and composition:** W2 §2.1, W7 §6.2, Givon–Kupferman–Stuart, the Mori–Zwanzig paper in direction 5, and the port-Hamiltonian survey in direction 9.

For additional community reports, the [DOE ASCR programme-document collection](https://science.osti.gov/ascr/Community-Resources/Program-Documents) and its [archive](https://science.osti.gov/ascr/Community-Resources/Program-Documents/ASCR-Program-Documents-Archive) are useful discovery points. New entries there should be read and dated before being used to update this review. The surveys above are entry points to primary results, not substitutes for the focused novelty review required by a publishable agenda.

[W1]: https://www.nationalacademies.org/read/15269
[W2]: https://www.osti.gov/servlets/purl/944335
[W3]: https://science.osti.gov/-/media/ascr/pdf/research/am/docs/EMWGreport.pdf
[W4]: https://www.nationalacademies.org/read/13395/chapter/9
[W5]: https://arxiv.org/abs/1610.02608
[W6]: https://www.osti.gov/biblio/1478744
[W7]: https://eu-maths-in.eu/wp-content/uploads/EU-MATHS-IN-Strategic-Research-Agenda-2020.pdf
[W8]: https://www.nationalacademies.org/read/26894/chapter/10
[W9]: https://arxiv.org/abs/2104.11079
