document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const youtubeUrlInput = document.getElementById('youtubeUrl');
    const btnFetchInfo = document.getElementById('btnFetchInfo');
    const videoInfoBox = document.getElementById('videoInfoBox');
    const videoThumb = document.getElementById('videoThumb');
    const videoTitle = document.getElementById('videoTitle');
    const videoDuration = document.getElementById('videoDuration');

    const dropZone = document.getElementById('dropZone');
    const imageInput = document.getElementById('imageInput');
    const dropZoneContent = document.getElementById('dropZoneContent');
    const imagePreviewBox = document.getElementById('imagePreviewBox');
    const imagePreview = document.getElementById('imagePreview');
    const btnRemoveImg = document.getElementById('btnRemoveImg');

    const layoutCards = document.querySelectorAll('.layout-card');
    const btnSubmit = document.getElementById('btnSubmit');

    // Advanced Settings Elements
    const toggleSettings = document.getElementById('toggleSettings');
    const settingsContent = document.getElementById('settingsContent');
    const inputKeyTolerance = document.getElementById('inputKeyTolerance');
    const valKeyTolerance = document.getElementById('valKeyTolerance');
    const posOptions = document.querySelectorAll('.pos-option');
    const inputStartTime = document.getElementById('inputStartTime');
    const inputEndTime = document.getElementById('inputEndTime');

    const statusBox = document.getElementById('statusBox');
    const statusTitle = document.getElementById('statusTitle');
    const statusDesc = document.getElementById('statusDesc');

    const resultBox = document.getElementById('resultBox');
    const outputVideoPlayer = document.getElementById('outputVideoPlayer');
    const btnDownload = document.getElementById('btnDownload');

    let selectedFile = null;

    // Toggle Settings Panel
    toggleSettings.addEventListener('click', () => {
        settingsContent.classList.toggle('hidden');
        const icon = toggleSettings.querySelector('.arrow-icon');
        if (icon) {
            icon.classList.toggle('fa-chevron-down');
            icon.classList.toggle('fa-chevron-up');
        }
    });

    // Key Tolerance Slider
    inputKeyTolerance.addEventListener('input', (e) => {
        const val = Math.round(parseFloat(e.target.value) * 100);
        valKeyTolerance.textContent = `${val}%`;
    });

    // Position Selector
    posOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            posOptions.forEach(o => o.classList.remove('active'));
            opt.classList.add('active');
            const radio = opt.querySelector('input[type="radio"]');
            if (radio) radio.checked = true;
        });
    });

    // 1. Fetch YouTube Info
    btnFetchInfo.addEventListener('click', async () => {
        const url = youtubeUrlInput.value.trim();
        if (!url) {
            alert('يرجى إدخال رابط يوتيوب صحيح أولاً');
            return;
        }

        btnFetchInfo.disabled = true;
        btnFetchInfo.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> جاري التحقق...';

        try {
            const response = await fetch(`/api/info?url=${encodeURIComponent(url)}`);
            const data = await response.json();

            if (data.success) {
                videoThumb.src = data.info.thumbnail || '';
                videoTitle.textContent = data.info.title || 'مقطع يوتيوب';
                videoDuration.innerHTML = `<i class="fa-regular fa-clock"></i> المدة: ${data.info.duration_string}`;
                videoInfoBox.classList.remove('hidden');
            } else {
                alert('تعذر جلب معلومات المقطع. تأكد من صحة الرابط.');
            }
        } catch (err) {
            alert('حدث خطأ في الاتصال بالخادم.');
        } finally {
            btnFetchInfo.disabled = false;
            btnFetchInfo.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> فحص الرابط';
        }
    });

    // 2. Drag & Drop Image Handling
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('drag-over'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('drag-over'), false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files && files.length > 0) {
            handleImageFile(files[0]);
        }
    });

    imageInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleImageFile(e.target.files[0]);
        }
    });

    function handleImageFile(file) {
        if (!file.type.startsWith('image/')) {
            alert('يرجى اختيار ملف صورة صالح (JPG, PNG, WEBP)');
            return;
        }
        selectedFile = file;
        try {
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            imageInput.files = dataTransfer.files;
        } catch (err) {
            console.log('DataTransfer fallback', err);
        }
        const reader = new FileReader();
        reader.onload = (e) => {
            imagePreview.src = e.target.result;
            dropZoneContent.classList.add('hidden');
            imagePreviewBox.classList.remove('hidden');
        };
        reader.readAsDataURL(file);
    }

    btnRemoveImg.addEventListener('click', (e) => {
        e.stopPropagation();
        selectedFile = null;
        imageInput.value = '';
        imagePreview.src = '';
        imagePreviewBox.classList.add('hidden');
        dropZoneContent.classList.remove('hidden');
    });

    // 3. Layout Selector Cards
    layoutCards.forEach(card => {
        card.addEventListener('click', () => {
            layoutCards.forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            const radio = card.querySelector('input[type="radio"]');
            if (radio) radio.checked = true;
        });
    });

    // 4. Submit & Processing Logic
    btnSubmit.addEventListener('click', async () => {
        const youtubeUrl = youtubeUrlInput.value.trim();
        if (!youtubeUrl) {
            alert('يرجى إدخال رابط فيديو اليوتيوب أولاً');
            youtubeUrlInput.focus();
            return;
        }
        
        const fileToUpload = selectedFile || (imageInput.files && imageInput.files[0]);
        if (!fileToUpload) {
            alert('يرجى رفع الصورة المطلوبة');
            return;
        }

        const layoutSelect = document.getElementById('layoutSelect');
        const selectedLayout = layoutSelect ? layoutSelect.value : (document.querySelector('input[name="layout"]:checked') ? document.querySelector('input[name="layout"]:checked').value : 'black_screen_transparent');
        const keyTolerance = inputKeyTolerance ? inputKeyTolerance.value : 0.25;
        const selectedPosRadio = document.querySelector('input[name="video_position"]:checked');
        const videoPosition = selectedPosRadio ? selectedPosRadio.value : 'center';
        const startTime = inputStartTime ? (inputStartTime.value || 0) : 0;
        const endTime = inputEndTime ? (inputEndTime.value || '') : '';

        // UI Reset
        btnSubmit.disabled = true;
        const statusMessage = document.getElementById('statusMessage');
        const progressBar = document.getElementById('progressBar');
        const steps = document.querySelectorAll('.step');
        const errorBox = document.getElementById('errorBox');
        
        if (errorBox) errorBox.classList.add('hidden');
        statusBox.classList.remove('hidden');
        resultBox.classList.add('hidden');
        
        if (statusMessage) statusMessage.textContent = 'يتم تحضير الملفات لبدء المعالجة...';
        if (progressBar) progressBar.style.width = '10%';
        if (steps && steps.length > 0) {
            steps.forEach(s => s.classList.remove('active', 'completed'));
            steps[0].classList.add('active');
        }

        statusBox.scrollIntoView({ behavior: 'smooth' });

        // Prepare Form Data
        const formData = new FormData();
        formData.append('youtube_url', youtubeUrl);
        formData.append('image', fileToUpload);
        formData.append('layout', selectedLayout);
        formData.append('key_tolerance', keyTolerance);
        formData.append('video_position', videoPosition);
        formData.append('start_time', startTime);
        if (endTime) {
            formData.append('end_time', endTime);
        }

        try {
            const response = await fetch('/api/generate', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success && data.task_id) {
                pollTaskStatus(data.task_id);
            } else {
                showError(data.detail || 'فشل بدء الطلب. يرجى المحاولة مرة أخرى.');
            }
        } catch (err) {
            showError('تعذر الاتصال بالخادم. تأكد من أن الموقع يعمل وحدّث الصفحة (F5).');
        }
    });

    function pollTaskStatus(taskId) {
        const MAX_POLLING_ATTEMPTS = 300; // 10 minutes at 2s interval
        const MAX_CONSECUTIVE_ERRORS = 5;
        let pollCount = 0;
        let errorCount = 0;

        const interval = setInterval(async () => {
            pollCount++;

            if (pollCount >= MAX_POLLING_ATTEMPTS) {
                clearInterval(interval);
                showError('انتهى وقت الانتظار. استغرقت العملية وقتاً أطول من المعتاد.');
                return;
            }

            try {
                const res = await fetch(`/api/status/${taskId}`);
                if (!res.ok) throw new Error('Network response was not ok');
                const data = await res.json();
                
                // Reset error count on successful request
                errorCount = 0; 

                if (data.status === 'downloading') {
                    statusMessage.textContent = data.message;
                    progressBar.style.width = '30%';
                    steps[0].classList.add('active');
                } else if (data.status === 'processing') {
                    statusMessage.textContent = data.message;
                    progressBar.style.width = '70%';
                    steps[0].classList.replace('active', 'completed');
                    steps[1].classList.add('active');
                } else if (data.status === 'completed') {
                    clearInterval(interval);
                    progressBar.style.width = '100%';
                    steps[1].classList.replace('active', 'completed');
                    steps[2].classList.add('completed');
                    
                    setTimeout(() => {
                        statusBox.classList.add('hidden');
                        resultBox.classList.remove('hidden');
                        downloadBtn.href = data.download_url;
                        btnSubmit.disabled = false;
                        resultBox.scrollIntoView({ behavior: 'smooth' });
                    }, 1000);
                    
                } else if (data.status === 'failed') {
                    clearInterval(interval);
                    showError(data.message || 'حدث خطأ أثناء المعالجة.');
                }
            } catch (e) {
                console.error('Polling error:', e);
                errorCount++;
                if (errorCount >= MAX_CONSECUTIVE_ERRORS) {
                    clearInterval(interval);
                    showError('فقد الاتصال بالخادم. يرجى المحاولة مرة أخرى.');
                }
            }
        }, 2000);
    }

    function showError(msg) {
        statusBox.classList.add('hidden');
        const errorBox = document.getElementById('errorBox');
        const errorMessage = document.getElementById('errorMessage');
        if (errorBox && errorMessage) {
            errorMessage.textContent = msg;
            errorBox.classList.remove('hidden');
            errorBox.scrollIntoView({ behavior: 'smooth' });
        } else {
            alert(msg);
        }
        btnSubmit.disabled = false;
    }
});
