

## 1. FPGA-based RF signal classification via reservoir computing

**Title:** "RF Signal Classification using Boolean Reservoir Computing on an FPGA"   
**Authors:** Heidi Komkov, Liam Pocher, Alessandro Restelli, Brian Hunt, Daniel Lathrop   
**Conference:** 2021 International Joint Conference on Neural Networks (IJCNN), July 2021   
**DOI:** 10.1109/IJCNN52387.2021.9533342   
**IEEE Xplore:** https://ieeexplore.ieee.org/document/9533342/   

**Relevance:** This paper implements hardware-accelerated reservoir computing using unclocked Boolean logic gate networks on a PYNQ-Z1 FPGA (Xilinx Zynq) for classifying RF modulation types from the DeepSig 2016 dataset. It achieves accuracy competitive with CNNs while using far fewer trainable parameters, demonstrating a resource-efficient ML approach directly applicable to the Artix-7 FPGA's constrained logic resources. The work validates that lightweight ML architectures can perform real-time RF signal classification in programmable logic.

**Topics covered:** FPGA-based RF signal processing and classification (T1), FPGA-accelerated ML inference (T5)

---

## 2. Angle-of-arrival estimation with FPGA-accelerated ML

**Title:** "A Study of Angle of Arrival Estimation of a RF Signal with FPGA Acceleration"   
**Authors:** Jin Feng Lin, Todd Morehouse, Charles Montes, Erika Caushi, Artem Dudko, Eric Savage, Ruolin Zhou   
**Conference:** 2024 International Wireless Communications and Mobile Computing Conference (IWCMC), pp. 1625–1630   
**DOI:** 10.1109/IWCMC61514.2024.10592551   
**IEEE Xplore:** https://ieeexplore.ieee.org/document/10592551/   

**Relevance:** This paper compares traditional DSP algorithms (MUSIC, ESPRIT) with ML techniques (ANNs, CNNs) for angle-of-arrival estimation of RF signals, accelerated on FPGA hardware. The ML approaches demonstrate superior robustness under multipath fading conditions. This is directly relevant to the capstone's integration of ML-based RF signal processing on FPGA, illustrating how both classical DSP and neural network inference pipelines can coexist in a unified FPGA architecture.

**Topics covered:** FPGA-based RF signal processing (T1), ML for RF signal classification on edge platforms (T2), FPGA-accelerated ML inference (T5)

---

## 3. Streaming CNN on FPGA for real-time modulation classification

**Title:** "Streaming Convolutional Neural Network FPGA Architecture for RFSoC Data Converters"   
**Authors:** Andrew MacLellan, Louise H. Crockett, Robert W. Stewart   
**Conference:** 21st IEEE Interregional New Circuits and Systems Conference (IEEE NEWCAS 2023), Edinburgh, UK, June 2023   
**IEEE Xplore:** https://ieeexplore.ieee.org/document/10198198/   

**Relevance:** This paper presents a fully streaming CNN architecture deployed on an AMD RFSoC FPGA for continuous, sample-by-sample automatic modulation classification at 128 MHz sampling frequency. The design uses GEMM transforms, on-chip weight storage, and 18-bit fixed-point arithmetic while consuming only ~10% of DSP slices and ~15% of BRAMs. This work directly addresses the capstone's need for a real-time ML inference pipeline on FPGA, demonstrating how to architect a streaming processing chain from ADC input through neural network classification — a model for the Artix-7 implementation. The associated open-source tools and "DeepRFSoC" dataset provide practical reference material.

**Topics covered:** FPGA-accelerated ML inference (T5), real-time processing pipelines on FPGA (T7), automatic modulation classification with deep learning (T8)

---

## 4. Comparative deep learning architectures for automatic modulation classification

**Title:** "Automatic Modulation Classification in Deep Learning"   
**Authors:** Khawla A. Alnajjar, Sara Ghunaim, Sam Ansari   
**Conference:** 2022 5th International Conference on Communications, Signal Processing, and their Applications (ICCSPA), Cairo, Egypt, December 2022   
**DOI:** 10.1109/ICCSPA55860.2022.10019122   
**IEEE Xplore:** https://ieeexplore.ieee.org/document/10019122/   

**Relevance:** This paper provides an empirical comparison of three deep learning architectures — deep neural networks (DNN), convolutional neural networks (CNN), and deep belief networks (DBN) — for automatic modulation classification. The comparative framework is valuable for the capstone project's ML pipeline design, offering guidance on selecting the optimal DL architecture when targeting resource-constrained deployment platforms like the STM32 or Artix-7 FPGA. Understanding the accuracy-complexity tradeoffs across architectures informs which model topology to deploy at the edge.

**Topics covered:** Automatic modulation classification using deep learning (T8)

---

## 5. CNN-based LoRa spreading factor detection from spectrograms

**Title:** "Deep Learning Enhanced Spectrum Sensing for LoRa Spreading Factor Detection"   
**Authors:** P. M. Mutescu, A. Lavric, A. I. Petrariu, V. Popa   
**Conference:** 2023 13th International Symposium on Advanced Topics in Electrical Engineering (ATEE), Bucharest, Romania, March 2023   
**DOI:** 10.1109/ATEE58038.2023.10108224   
**IEEE Xplore:** https://ieeexplore.ieee.org/document/10108224/   

**Relevance:** This paper proposes a CNN-based LoRa spreading factor (SF) detection scheme that converts received LoRa signals into spectrograms and classifies them using a convolutional neural network, addressing spectrum occupancy awareness and collision mitigation. This is directly applicable to the capstone's ML-driven LoRa signal classification pipeline, demonstrating how spectrogram representations of LoRa chirp signals serve as effective input features for deep learning classifiers — a technique transferable to the project's FPGA-based signal ingestion and classification system.

**Topics covered:** LoRa signal processing, detection, and classification (T3)

---

## 6. Deep learning for LoRa device identification and rogue signal detection

**Title:** "Adversarial Attacks on LoRa Device Identification and Rogue Signal Detection with Deep Learning"   
**Authors:** Yalin E. Sagduyu, Tugba Erpek   
**Conference:** MILCOM 2023 — 2023 IEEE Military Communications Conference, Boston, MA, October–November 2023, pp. 385–390   
**DOI:** 10.1109/MILCOM58377.2023.10356224   
**IEEE Xplore:** https://ieeexplore.ieee.org/document/10356224/   

**Relevance:** This paper develops a deep learning framework for two LoRa signal classification tasks — device identification and legitimate-versus-rogue device classification — using CNNs and feedforward neural networks trained on real experimental I/Q data from LoRa transmitters. It also investigates adversarial robustness using FGSM attacks. The work is highly relevant to the capstone's goal of ML-driven LoRa signal classification and device identification from I/Q data captured by the LoRa transceiver modules, and raises important considerations about classifier robustness in real-world RF environments.

**Topics covered:** ML for RF signal classification and emitter identification (T2), LoRa signal classification (T3)

---

## 7. LoRa gateway implementation on SoC FPGA

**Title:** "LoRa Gateway Based on SoC FPGA Platforms"   
**Authors:** Tan-Phat Dang, Tuan-Kiet Tran, Trong-Tu Bui, Huu-Thuan Huynh   
**Conference:** 2021 International Symposium on Electrical and Electronics Engineering (ISEE), pp. 48–52   
**DOI:** 10.1109/ISEE51682.2021.9418711   
**IEEE Xplore:** https://ieeexplore.ieee.org/document/9418711/   

**Relevance:** This paper implements a single-channel LoRa gateway on a DE10-Nano SoC FPGA platform, combining an ARM Cortex-A9 processor with custom FPGA logic for hardware-accelerated AES-128 encryption via DMA, achieving 1200 Mbps bandwidth at 150 MHz. The architecture — pairing a soft processor with custom programmable logic for LoRa data handling — provides a directly analogous design reference for the capstone's Artix-7 FPGA-based LoRa signal processing, demonstrating how SoC FPGA platforms handle LoRa communication with hardware acceleration.

**Topics covered:** FPGA-based RF signal processing (T1), LoRa signal processing (T3)

---

## 8. Neural network-based LoRa demodulation from time-domain I/Q data

**Title:** "LoRa Signal Demodulation Using Deep Learning, a Time-Domain Approach"   
**Authors:** Kosta Dakic, Bassel Al Homssi, Akram Al-Hourani, Margaret Lech   
**Conference:** 2021 IEEE 93rd Vehicular Technology Conference (VTC2021-Spring)   
**DOI:** 10.1109/VTC2021-Spring51267.2021.9448711   
**IEEE Xplore:** https://ieeexplore.ieee.org/document/9448711/   

**Relevance:** This paper uses CNNs to demodulate LoRa symbols directly from time-domain I/Q data, training on emulated LoRa symbols under various channel impairments (AWGN, carrier frequency offset, time offset). Results show deep learning outperforms conventional non-coherent LoRa detection and approaches matched-filter performance. This validates the feasibility of replacing traditional LoRa demodulation with neural networks operating on raw I/Q samples — a core concept in the capstone's AI-driven signal processing pipeline where ML models process signals captured from the LoRa transceivers.

**Topics covered:** ML for RF signal classification on edge platforms (T2), LoRa signal processing and detection (T3)

---

## 9. Cloud-based open-source FPGA toolchain for digital design education

**Title:** "Digital Design Education Using an Open-Source, Cloud-Based FPGA Toolchain"   
**Authors:** Weston Smith, Zachary Driskill, Jeffrey Goeders, Michael Wirthlin   
**Conference:** 2024 IEEE Intermountain Engineering, Technology and Computing Conference (i-ETC), May 2024   
**IEEE Xplore:** https://ieeexplore.ieee.org/abstract/document/10564285   

**Relevance:** This paper presents an educational framework for teaching digital design using cloud-based resources and open-source FPGA tools delivered via Google Colab notebooks, with labs covering arithmetic circuits, combinational and sequential logic, and finite state machines. The framework-based, accessible approach to FPGA education directly supports the capstone project's pedagogical goals, demonstrating how FPGA design instruction can be structured for maximum student accessibility and engagement — a model for the capstone's own educational framework integrating FPGA design with RF and ML.

**Topics covered:** Educational frameworks integrating FPGA and digital design (T4)

---

## 10. STM32 Nucleo platform programming for IoT education

**Title:** "Programming STM32 Nucleo Platform for IoT Education Using STM32duino and Mbed OS"   
**Authors:** N. O. Strelkov, V. V. Krutskikh, E. V. Shalimova   
**Conference:** 2022 VI International Conference on Information Technologies in Engineering Education (Inforino), April 2022   
**DOI:** 10.1109/Inforino53888.2022.9782920   
**IEEE Xplore:** https://ieeexplore.ieee.org/document/9782920/   

**Relevance:** This paper evaluates the STM32 Nucleo-64 F446RE board for IoT education using STM32duino and Mbed OS programming environments, presenting programs for Ethernet, Bluetooth, and Wi-Fi communication and comparing the Nucleo platform with Arduino boards. This directly supports the capstone project's embedded systems education component, demonstrating how STM32 Nucleo-based platforms can be effectively integrated into engineering teaching — particularly relevant given the project's use of the STM32 Nucleo-L476RG for RF beacon transmission and embedded processing.

**Topics covered:** Educational frameworks integrating embedded systems (T4), STM32/microcontroller-based RF systems (T6)

---

## Topic coverage summary

The 10 papers provide coverage across all eight specified topic areas:

| Topic area | Papers |
|---|---|
| T1: FPGA-based RF signal processing and classification | Papers 1, 2, 3, 7 |
| T2: ML for RF classification / emitter ID (edge/embedded) | Papers 2, 6, 8 |
| T3: LoRa signal processing, detection, classification | Papers 5, 6, 7, 8 |
| T4: Educational frameworks (FPGA, embedded, RF, ML) | Papers 9, 10 |
| T5: FPGA-accelerated ML inference for signal processing | Papers 1, 2, 3 |
| T6: STM32 / microcontroller-based RF systems | Paper 10 |
| T7: Real-time processing pipelines on FPGA | Paper 3 |
| T8: Automatic modulation classification with deep learning | Papers 3, 4 |
