kernel void eval(unsigned int stride, unsigned int dataLength, unsigned int lim0, unsigned int lim1, global const float *observed, global const float *simulated, global float *errorSumOut, global int *nonExceedanceSumOut) {
	//, local float *localObserved

	int gId0 = get_global_id(0);
	int gId1 = get_global_id(1);
	int lId0 = get_local_id(0);
	int lId1 = get_local_id(1);
	int gDataRow;
	//int lDataRow;
	int gSimulatedRow;
	int gOutRow;

	float errorSum=0;
	int notExceededSum=0;

	gDataRow=gId0*stride;
	//lDataRow=lId0*stride;
	gSimulatedRow=gId1*dataLength+gId0*stride;
	gOutRow=gId1*(get_global_size(0))+gId0;
	
	if (gId1<lim1 && gId0<(lim0-1)) {
		// Compute metrics
		for (int i0=0; i0<stride; i0++) {
			errorSum+=pow(observed[gDataRow+i0]-simulated[gSimulatedRow+i0],2);
			notExceededSum+=observed[gDataRow+i0]<=simulated[gSimulatedRow+i0];
		}

		errorSumOut[gOutRow]=errorSum;
		nonExceedanceSumOut[gOutRow]=notExceededSum;
	} else if (gId1<lim1 && gId0<lim0) {
		for (int i0=0; gDataRow+i0<dataLength; i0++) {
			errorSum+=pow(observed[gDataRow+i0]-simulated[gSimulatedRow+i0],2);
			notExceededSum+=observed[gDataRow+i0]<=simulated[gSimulatedRow+i0];
		}

		errorSumOut[gOutRow]=errorSum;
		nonExceedanceSumOut[gOutRow]=notExceededSum;
	}
}
