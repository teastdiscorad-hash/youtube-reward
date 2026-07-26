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
    const keyTolerance = document.getElementById('keyTolerance');
    const toleranceVal = document.getElementById('toleranceVal');

    // Accordion Toggle
    const toggleSettings = document.getElementById('toggleSettings');
    const settingsContent = document.getElementById('settingsContent');
    if (toggleSettings && settingsContent) {
        toggleSettings.addEventListener('click', () => {
            settingsContent.classList.toggle('hidden');
            const icon = toggleSettings.querySelector('.arrow-icon');
            if (icon) {
                icon.classList.toggle('fa-chevron-down');
                icon.classList.toggle('fa-chevron-up');
            }
        });
    }

    const startTime = document.getElementById('startTime');
    const endTime = document.getElementById('endTime');
    const btnSubmit = document.getElementById('btnSubmit');

    const statusBox = document.getElementById('statusBox');
    const statusMessage = document.getElementById('statusMessage');
    const progressBar = document.getElementById('progressBar');

    const steps = [
        document.querySelector('.step-1'),
        document.querySelector('.step-2'),
        document.querySelector('.step-3')
    ];

    const resultBox = document.getElementById('resultBox');
    const outputVideoPlayer = document.getElementById('outputVideoPlayer');
    const downloadBtn = document.getElementById('downloadBtn');
    const errorBox = document.getElementById('errorBox');
    const errorMessage = document.getElementById('errorMessage');

    let selectedFile = null;

    // Update tolerance display
    if (keyTolerance && toleranceVal) {
        keyTolerance.addEventListener('input', (e) => {
            toleranceVal.textContent = e.target.value;
        });
    }

    // Layout Selector Cards
    if (layoutCards && layoutCards.length > 0) {
        layoutCards.forEach(card => {
            card.addEventListener('click', () => {
                layoutCards.forEach(c => c.classList.remove('active'));
                card.classList.add('active');
                const radio = card.querySelector('input[type="radio"]');
                if (radio) radio.checked = true;
            });
        });
    }

    // Position Options
    const posOptions = document.querySelectorAll('.pos-option');
    posOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            posOptions.forEach(o => o.classList.remove('active'));
            opt.classList.add('active');
            const radio = opt.querySelector('input[type="radio"]');
            if (radio) radio.checked = true;
        });
    });

    // 1. Fetch YouTube Info Listener
    if (btnFetchInfo && youtubeUrlInput) {
        btnFetchInfo.addEventListener('click', async () => {
            const url = youtubeUrlInput.value.trim();
            if (!url) {
                alert('يرجى إدخال رابط يوتيوب صحيح أولاً');
                youtubeUrlInput.focus();
                return;
            }

            btnFetchInfo.disabled = true;
            btnFetchInfo.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> جاري الفحص...';

            try {
                const response = await fetch(`/api/info?url=${encodeURIComponent(url)}`);
                const data = await response.json();

                if (data.success && data.info) {
                    if (videoThumb) videoThumb.src = data.info.thumbnail || '';
                    if (videoTitle) videoTitle.textContent = data.info.title || 'مقطع يوتيوب';
                    if (videoDuration) videoDuration.textContent = data.info.duration_string || 'جاهز للدمج';
                    if (videoInfoBox) videoInfoBox.classList.remove('hidden');
                } else {
                    alert('تعذر جلب معلومات المقطع. يمكنك متابعة العملية والضغط على بدء الدمج مباشرة.');
                }
            } catch (err) {
                console.error('Fetch info error:', err);
                alert('تعذر جلب المعلومات تلقائياً. يمكنك الاستمرار في العملية بالضغط على زر الدمج.');
            } finally {
                btnFetchInfo.disabled = false;
                btnFetchInfo.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> فحص الرابط';
            }
        });
    }

    // 2. Drag & Drop Image Handling
    if (dropZone && imageInput) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.add('drag-over'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.remove('drag-over'), false);
        });

        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt ? dt.files : null;
            if (files && files.length > 0) {
                handleImageFile(files[0]);
            }
        });

        imageInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handleImageFile(e.target.files[0]);
            }
        });
    }

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
            console.log('Fallback DataTransfer handling');
        }
        const reader = new FileReader();
        reader.onload = (e) => {
            if (imagePreview) imagePreview.src = e.target.result;
            if (dropZoneContent) dropZoneContent.classList.add('hidden');
            if (imagePreviewBox) imagePreviewBox.classList.remove('hidden');
        };
        reader.readAsDataURL(file);
    }

    if (btnRemoveImg) {
        btnRemoveImg.addEventListener('click', (e) => {
            e.stopPropagation();
            selectedFile = null;
            if (imageInput) imageInput.value = '';
            if (imagePreview) imagePreview.src = '';
            if (imagePreviewBox) imagePreviewBox.classList.add('hidden');
            if (dropZoneContent) dropZoneContent.classList.remove('hidden');
        });
    }

    // 3. Submit Form Listener
    if (btnSubmit) {
        btnSubmit.addEventListener('click', async () => {
            const youtubeUrl = youtubeUrlInput ? youtubeUrlInput.value.trim() : '';
            if (!youtubeUrl) {
                alert('يرجى إدخال رابط فيديو اليوتيوب أولاً');
                if (youtubeUrlInput) youtubeUrlInput.focus();
                return;
            }
            
            const fileToUpload = selectedFile || (imageInput && imageInput.files ? imageInput.files[0] : null);
            if (!fileToUpload) {
                alert('يرجى رفع الصورة الخلفية المطلوبة');
                return;
            }

            const selectedLayoutRadio = document.querySelector('input[name="layout"]:checked');
            const selectedLayout = selectedLayoutRadio ? selectedLayoutRadio.value : 'black_screen_transparent';
            const tol = keyTolerance ? keyTolerance.value : 0.25;
            const selectedPosRadio = document.querySelector('input[name="video_position"]:checked');
            const videoPosition = selectedPosRadio ? selectedPosRadio.value : 'center';
            const sTime = startTime ? (startTime.value || 0) : 0;
            const eTime = endTime ? (endTime.value || '') : '';

            // Reset UI States
            btnSubmit.disabled = true;
            
            if (errorBox) errorBox.classList.add('hidden');
            if (statusBox) statusBox.classList.remove('hidden');
            if (resultBox) resultBox.classList.add('hidden');
            
            if (statusMessage) statusMessage.textContent = 'يتم تحضير الملفات لبدء المعالجة...';
            if (progressBar) progressBar.style.width = '10%';
            if (steps) {
                steps.forEach(s => s && s.classList.remove('active', 'completed'));
                if (steps[0]) steps[0].classList.add('active');
            }

            statusBox.scrollIntoView({ behavior: 'smooth' });

            // Form Data
            const formData = new FormData();
            formData.append('youtube_url', youtubeUrl);
            formData.append('image', fileToUpload);
            formData.append('layout', selectedLayout);
            formData.append('key_tolerance', tol);
            formData.append('video_position', videoPosition);
            formData.append('start_time', sTime);
            if (eTime) {
                formData.append('end_time', eTime);
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
                console.error('Submit error:', err);
                showError('تعذر الاتصال بالخادم. تأكد من عمل الشبكة وأعد المحاولة.');
            }
        });
    }

    // Polling Loop with Safety Limit
    function pollTaskStatus(taskId) {
        const MAX_POLLING_ATTEMPTS = 300;
        const MAX_CONSECUTIVE_ERRORS = 5;
        let pollCount = 0;
        let errorCount = 0;

        const interval = setInterval(async () => {
            pollCount++;

            if (pollCount >= MAX_POLLING_ATTEMPTS) {
                clearInterval(interval);
                showError('استغرقت العملية وقتاً أطول من المعتاد. يرجى المحاولة مرة أخرى.');
                return;
            }

            try {
                const res = await fetch(`/api/status/${taskId}`);
                if (!res.ok) throw new Error('Network response failure');
                const data = await res.json();
                
                errorCount = 0; 

                if (data.status === 'downloading') {
                    if (statusMessage) statusMessage.textContent = data.message || 'جاري تحميل المقطع...';
                    if (progressBar) progressBar.style.width = '35%';
                    if (steps && steps[0]) steps[0].classList.add('active');
                } else if (data.status === 'processing') {
                    if (statusMessage) statusMessage.textContent = data.message || 'جاري الدمج وتفريغ السواد...';
                    if (progressBar) progressBar.style.width = '75%';
                    if (steps && steps[0]) steps[0].classList.replace('active', 'completed');
                    if (steps && steps[1]) steps[1].classList.add('active');
                } else if (data.status === 'completed') {
                    clearInterval(interval);
                    if (progressBar) progressBar.style.width = '100%';
                    if (steps && steps[1]) steps[1].classList.replace('active', 'completed');
                    if (steps && steps[2]) steps[2].classList.add('completed');
                    
                    setTimeout(() => {
                        if (statusBox) statusBox.classList.add('hidden');
                        if (resultBox) resultBox.classList.remove('hidden');
                        if (downloadBtn) downloadBtn.href = data.download_url;
                        if (outputVideoPlayer) {
                            outputVideoPlayer.src = data.download_url;
                            outputVideoPlayer.load();
                        }
                        if (btnSubmit) btnSubmit.disabled = false;
                        resultBox.scrollIntoView({ behavior: 'smooth' });
                    }, 800);
                    
                } else if (data.status === 'failed') {
                    clearInterval(interval);
                    showError(data.message || 'تعذر معالجة المقطع. تأكد من صحة الرابط.');
                }
            } catch (e) {
                console.error('Polling error:', e);
                errorCount++;
                if (errorCount >= MAX_CONSECUTIVE_ERRORS) {
                    clearInterval(interval);
                    showError('فقد الاتصال بالخادم أثناء المعالجة.');
                }
            }
        }, 1000);
    }

    function showError(msg) {
        if (statusBox) statusBox.classList.add('hidden');
        if (errorBox && errorMessage) {
            errorMessage.textContent = msg;
            errorBox.classList.remove('hidden');
            errorBox.scrollIntoView({ behavior: 'smooth' });
        } else {
            alert(msg);
        }
        if (btnSubmit) btnSubmit.disabled = false;
    }
});
