#!/bin/bash
head -108001 EventLEDlistQECos2DeltaPhiDataGen_50000_0_180_0_15_0_15_-180_180_Ent | tail -108000 > PET_ungated.dat
head -108001 EventLEDlistQECos2DeltaPhiDataGen_50000_72_92_7_8_7_8_0_0_Rand       | tail -108000 > PET_gated_rand.dat
head -108001 EventLEDlistQECos2DeltaPhiDataGen_50000_72_92_7_8_7_8_0_0_Ent        | tail -108000 > PET_gated_ent.dat

sed -i 's/365,1,/365,3,/g' PET_ungated.dat 
sed -i 's/365,1,/365,4,/g' PET_gated_rand.dat 
sed -i 's/365,1,/365,5,/g' PET_gated_ent.dat 
sed -i 's/365,0,/365,1,/g' PET_gated_rand.dat 
sed -i 's/365,0,/365,2,/g' PET_gated_ent.dat 

cat PET_ungated.dat PET_gated_rand.dat PET_gated_ent.dat > big_demo.dat
