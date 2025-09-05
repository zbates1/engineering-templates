

# Project Proposal: Process Control for OCT-In-The-Loop Bioprinting
**TL;DR.** Investigating process innovations in extrusion bioprinting, with emphasis on closed-loop control using OCT imaging to dynamically tune construct mechanics and fidelity.

## Objective
Develop and demonstrate a **closed-loop control system** that uses OCT feedback to actively tune the crosslinking, degradation, or chemical stiffening of FRESH/volumetric bioprinted constructs during print.

## Background & Prior Work
- Process innovations are highlighted in [@bakirci2025] under *2.2 Engineering advances* and *2.3 Process Control and improvements*.
- Embedded OCT has been shown for monitoring in FRESH [@bakirci2025,@tashman20222], but no fully integrated feedback-control loop yet.
- Photodegradable hydrogels (embedded nitrobenzyl ether into the hydrogel) can dynamically soften under specific light exposure [@kloxin2009].
- Embedded Extrusion-Volumetric Printing (EmVP) demonstrates multi-material constructs using photo-crosslinkable micro-resins, GelMA-based µResins [@ribezzi2023].
- Microfluidics approaches using EDC/NHS as a cross-linker to increase stiffness (highly aligned fibrillar structure) [@shepherd2015,@omobono2015]. However, the exposure time will need to be flushed out as literature include times as between 0.5hr to 48hr to achieve optimal results and crosslinking [@omobono2015,@alavarse2022crosslinkers]. Cytotoxicity isn't a concern as long as standard protocols are follows [@lai2013corneal]. Additionally, a correct ratio will likely need to be experimented for with FRESH, but other applications found a optimum NHS/EDC molar ratio was 0.5 [@alavarse2022crosslinkers,@lai2013corneal].

## Specific Aims
**Aim 1.** Develop computer vision ML algorithm to determine interventions.  
**Aim 2.** Integrate OCT into the print path for real-time error detection.  
**Aim 3.** Demonstrate corrections using light (crosslink/degrade) or microfluidics (EDC/NHS).  

## Approach
### OCT-in-the-loop control
- OCT captures **layer height, pore geometry, void space**.

- Controller: PID/MPC based on OCT → mechanics calibration curve or CV algorithm → informed tuning of control knobs.

- Control knobs: light dose (405 nm ↑ stiffness), degrade dose (365 nm → soften), EDC/NHS microfluidics-assisted delivery (↑ stiffness), extrusion parameters.


## Risks & Mitigations
- **Nitrobenzyl polymerization toxicity** → cytocompatibility of PEG monoacrylate and free radical/ROS generation [@kloxin2009]
- **Spectral crosstalk** → orthogonality tests with 405 nm 1 W diode laser for EmVP and 365 nm diode laser for photodegrable nitrobenzyl polymer [@ribezzi2023,@kloxin2009]. For reference, at 10 mW/cm², nitrobenzyl hydrogels fully degrade in ~10 min at 365 nm (t = 280 s), in ~5 min at 20 mW/cm² (t = 140 s), but takes ~15–16 min at 405 nm (t = 930 s), meaning 405 nm works but is ~3–4× slower and less efficient than 365 nm [@kloxin2009].
- **Cell viability under near-UV/UV** → antioxidant additives to combat free radicals and ROS from photopolymerize or photodegrade, dose windows
- **EDC/NHS chemical crosslinking time** → exposure time for EDC/NHS, HEPES buffer solution to acheive desirable properties, optimal EDC/NHS molar ratio
- **OCT computer vision explainability** → SNR, false negatives + positives, print path adjustments

## Timeline & Milestones
| Quarter | Deliverables |
|---------|--------------|
| Q1      | Spectral/dose orthogonality test + exposure times for EDC/NHS chemical crosslinker |
| Q2      | OCT–mechanics calibration + model fit |
| Q3      | OCT-induced print planning edits |
| Q4      | FRESH with NB-µResin, volumetric editing with OCT feedback |

## Questions for Dr. Feinberg

1. **Do you have competitors in extrusion bioprinting?**  
   It seems like people use extrusion-based bioprinting and FRESH bioprinting interchangeably.  

2. **Does the needle geometry need to be tuned? Or is that a solved problem?**  
   I read that the 6-DOF helps with reducing the damage done by needles running through the construct.  

3. **Is there a need for post-processing bioreactors**  
   In the talks in this paper [@bakirci2025] about an integrated bioreactor setup, my understanding is that there would be an automated cell culture system that would then be sent into a bioink. 

4. **How is printing resolution lower than the bidirectional error of the stepper motor in this paper [@tashman2022]?**  
   I read *Development of a high-performance open-source 3D bioprinter* [@tashman2022] and I was wondering about the printing resolution. When the accuracy of the stepper motor was assessed, it was found that the bidirectional error was anywhere from 20 µm to 50 µm depending on the axis. However, then later it is said that the bioink printing resolution is approaching 20 µm.   

5. **Can you print the support bath in a nonplanar setup?**  
   In this paper [@tashman20222]:  

   > To date, FRESH and other embedded 3D bioprinting have used pre-filled containers of support material, whether the gelatin microparticle support bath or some other support bath such as alginate microparticles. However, for prints larger than ∼5 mm tall the deflection of the fine 34-gauge, 6.35 mm long needle tips limits resolution. We have previously overcome this by building custom needle tips with long, larger diameter and rigid tips terminated in a smaller diameter tip. However, printing into deep dishes of gelatin microparticle support bath presents other challenges such as dehydration and skinning of the upper layer of the gelatin microparticle support bath. Here we developed a new alternative approach by printing the gelatin microparticle support bath itself in order to minimize the deflection of the needle tip and without a limitation on construct height.  



## Future Investigations
- Investigate **2P degradation control** (740–800 nm) for spatially selective softening.  
- Feed mapping into **PID/MPC** controller for automated correction.


## Other Projects of High Interest

1. **Closed-loop bioink rheology system**  
   - Suggested by Annie, though Charlie noted shear damage may be less critical.  
   - ML/AI algorithms could be applied to rheology datasets [@bakirci2025], but challenges remain in generating sufficient sample sizes for biological contexts.  
   - Promising precedents exist in direct ink writing, where ML models have been trained to optimize ink rheology [@weeks2025].  

2. **Print planning software**  
   - Current nonplanar solutions are mostly custom and lack universality [@bakirci2025].  
    - There is a strong need for "automated trajectory generation from medical imaging data, including fiber orientation information [@bakirci2025]" to streamline planning and execution.
