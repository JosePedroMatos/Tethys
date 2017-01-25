kernel void ann(unsigned int inputDim, unsigned int nodes, unsigned int dataSize, unsigned int weightSize, global const float *data, global float *output, global float *weights, local float *localWeights) {
	int gId0 = get_global_id(0);
	int gId1 = get_global_id(1);
	int lId0 = get_local_id(0);
	int lId1 = get_local_id(1);
	int dataId = gId0*inputDim;
	int outId = gId1*dataSize+gId0;
	int lIdW = lId1*weightSize;
	float a;
	float b = 0;
	
	if (lId0==0) {
		int tmp = gId1 * weightSize;
		for (int i0=0; i0<(inputDim+2)*nodes+1; i0++) {
			localWeights[lIdW+i0]=weights[tmp+i0];
		}
	}
  
	barrier(CLK_LOCAL_MEM_FENCE);

	for (int i0=0; i0<nodes; i0++) {
		a=0;
		for (int i1=0; i1<inputDim; i1++) {
			a+=data[dataId+i1]*localWeights[lIdW+i1*nodes+i0];	//hidden layer weights
		}
		a+=localWeights[lIdW+nodes*inputDim+i0];				//hidden layer bias
		b+=localWeights[lIdW+nodes*(inputDim+1)+i0]*a;          //hidden layer activation and multiplication by output layer weights
	}
	b+=localWeights[lIdW+nodes*(inputDim+2)];					//output layer bias
  
	output[outId]=b;
}
